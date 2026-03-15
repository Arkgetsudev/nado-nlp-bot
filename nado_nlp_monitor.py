#!/usr/bin/env python3
import sys
import os
import json
import time
import requests
from datetime import datetime, timezone

print("=" * 50, flush=True)
print("  NADO NLP VAULT MONITOR", flush=True)
print("=" * 50, flush=True)

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHATS = [c.strip() for c in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",") if c.strip()]
POLL = int(os.environ.get("POLL_INTERVAL", "15"))
MIN_W = float(os.environ.get("MIN_WITHDRAWAL", "0"))
API = "https://gateway.prod.nado.xyz/v1/query"

print(f"  Token: {'SET' if TOKEN else 'MISSING'}", flush=True)
print(f"  Chats: {CHATS}", flush=True)
print(f"  Poll:  {POLL}s", flush=True)
print("=" * 50, flush=True)

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set", flush=True)
    sys.exit(1)
if not CHATS:
    print("ERROR: TELEGRAM_CHAT_IDS not set", flush=True)
    sys.exit(1)


def send_tg(msg):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    for cid in CHATS:
        try:
            r = requests.post(url, json={
                "chat_id": cid, "text": msg,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }, timeout=10)
            print(f"[TG] {cid}: {r.status_code}", flush=True)
        except Exception as e:
            print(f"[TG] {cid} error: {e}", flush=True)


def fetch():
    try:
        r = requests.get(
            f"{API}?type=nlp_pool_info",
            headers={"Accept-Encoding": "gzip, deflate"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
        print(f"[API] {r.status_code}: {r.text[:200]}", flush=True)
        return None
    except Exception as e:
        print(f"[API] error: {e}", flush=True)
        return None


def get_total(data):
    try:
        d = data
        if isinstance(d, dict) and "data" in d:
            d = d["data"]
        if isinstance(d, dict) and "result" in d:
            d = d["result"]
        if isinstance(d, list) and len(d) > 0:
            d = d[0]
        if isinstance(d, dict):
            print(f"[PARSE] Keys: {list(d.keys())}", flush=True)
            for k, v in d.items():
                print(f"[PARSE]   {k} = {str(v)[:100]}", flush=True)
        else:
            print(f"[PARSE] Type: {type(d)}, val: {str(d)[:200]}", flush=True)
            return None
        for key in ["total_quote", "total_deposits", "total_lp_deposits",
                     "total_assets", "total_quote_amount", "pool_total",
                     "tvl", "capacity", "total", "totalDeposits",
                     "total_value", "vault_total", "net_assets"]:
            if key in d:
                val = float(d[key])
                if val > 1e12:
                    return val / 1e18
                elif val > 1e4:
                    return val / 1e6
                return val
        return None
    except Exception as e:
        print(f"[PARSE] error: {e}", flush=True)
        return None


print("[*] Fetching initial state...", flush=True)
data = fetch()
if data:
    print(f"[+] Raw: {json.dumps(data)[:1000]}", flush=True)
else:
    print("[!] No data from API", flush=True)

prev = get_total(data) if data else None
if prev is not None:
    print(f"[+] Vault: {prev:,.2f} USDT0", flush=True)
else:
    print("[!] Could not parse vault total - check keys above", flush=True)

vault_str = f"{prev:,.2f}" if prev is not None else "unknown"
send_tg(
    "🟢 <b>Nado NLP Monitor Online</b>\n\n"
    "Vault: <b>" + vault_str + " USDT0</b>\n"
    "Polling every " + str(POLL) + "s"
)

print("[*] Monitoring...", flush=True)

errors = 0
wcount = 0

while True:
    try:
        time.sleep(POLL)
        data = fetch()
        if not data:
            errors += 1
            if errors == 10:
                send_tg("🔴 <b>Nado API unreachable</b>")
            continue
        errors = 0
        current = get_total(data)
        if current is None:
            continue
        if prev is not None:
            diff = current - prev
            if diff < 0 and abs(diff) >= MIN_W:
                wcount += 1
                amt = abs(diff)
                now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
                print(f"[ALERT #{wcount}] -{amt:,.2f} | {prev:,.2f} -> {current:,.2f}", flush=True)
                send_tg(
                    "🔔 <b>NLP Withdrawal Detected</b>\n\n"
                    "💰 <b>-" + f"{amt:,.2f}" + " USDT0</b>\n"
                    "📉 " + f"{prev:,.2f}" + " → " + f"{current:,.2f}" + " USDT0\n"
                    "🕐 " + now + "\n\n"
                    "👉 <a href='https://app.nado.xyz/vault'>Deposit now</a>"
                )
            elif diff > 0:
                t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"  [{t}] +{diff:,.2f} -> {current:,.2f}", flush=True)
        prev = current
    except KeyboardInterrupt:
        send_tg("🔴 <b>Nado NLP Monitor stopped</b>")
        sys.exit(0)
    except Exception as e:
        print(f"[!] {e}", flush=True)
        time.sleep(5)
