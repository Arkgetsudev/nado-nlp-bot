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

print("  Token: " + ("SET" if TOKEN else "MISSING"), flush=True)
print("  Chats: " + str(CHATS), flush=True)
print("  Poll:  " + str(POLL) + "s", flush=True)
print("=" * 50, flush=True)

if not TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN not set", flush=True)
    sys.exit(1)
if not CHATS:
    print("ERROR: TELEGRAM_CHAT_IDS not set", flush=True)
    sys.exit(1)


def send_tg(msg):
    url = "https://api.telegram.org/bot" + TOKEN + "/sendMessage"
    for cid in CHATS:
        try:
            r = requests.post(url, json={
                "chat_id": cid,
                "text": msg,
            }, timeout=10)
            print("[TG] " + cid + ": " + str(r.status_code), flush=True)
            if r.status_code != 200:
                print("[TG] Response: " + r.text[:200], flush=True)
        except Exception as e:
            print("[TG] " + cid + " error: " + str(e), flush=True)


def fetch():
    try:
        r = requests.get(
            API + "?type=nlp_pool_info",
            headers={"Accept-Encoding": "gzip, deflate"},
            timeout=15
        )
        if r.status_code == 200:
            return r.json()
        print("[API] " + str(r.status_code), flush=True)
        return None
    except Exception as e:
        print("[API] error: " + str(e), flush=True)
        return None


def get_total(data):
    """
    Parse vault total from Nado API response.
    Structure: { "status": "success", "data": { "nlp_pools": [ { "subaccount_info": { "healths": [ { "assets": "..." } ] } } ] } }
    The assets field in healths[0] represents the total vault value in x18.
    """
    try:
        pools = data.get("data", {}).get("nlp_pools", [])
        if not pools:
            print("[PARSE] No nlp_pools found", flush=True)
            return None

        pool = pools[0]
        sub_info = pool.get("subaccount_info", {})
        healths = sub_info.get("healths", [])

        if not healths:
            print("[PARSE] No healths found", flush=True)
            return None

        # healths[0] contains initial margin health with assets/liabilities
        assets_raw = healths[0].get("assets", "0")
        assets = float(assets_raw) / 1e18

        print("[PARSE] Assets: " + str(round(assets, 2)), flush=True)
        return assets

    except Exception as e:
        print("[PARSE] error: " + str(e), flush=True)
        return None


# Init
print("[*] Fetching initial state...", flush=True)
data = fetch()
prev = get_total(data) if data else None

if prev is not None:
    print("[+] Vault: " + str(round(prev, 2)) + " USDT0", flush=True)
else:
    print("[!] Could not parse vault total", flush=True)

vault_str = str(round(prev, 2)) if prev is not None else "unknown"
send_tg(
    "🟢 Nado NLP Monitor Online\n\n"
    "Vault: " + vault_str + " USDT0\n"
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
                send_tg("🔴 Nado API unreachable (10+ failed polls)")
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
                print("[ALERT #" + str(wcount) + "] -" + str(round(amt, 2)) + " | " + str(round(prev, 2)) + " -> " + str(round(current, 2)), flush=True)
                send_tg(
                    "🔔 NLP Withdrawal Detected!\n\n"
                    "💰 -" + str(round(amt, 2)) + " USDT0\n"
                    "📉 " + str(round(prev, 2)) + " → " + str(round(current, 2)) + " USDT0\n"
                    "🕐 " + now + "\n\n"
                    "👉 Deposit now: https://app.nado.xyz/vault"
                )
            elif diff > 0:
                t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print("  [" + t + "] +" + str(round(diff, 2)) + " -> " + str(round(current, 2)), flush=True)
        prev = current
    except KeyboardInterrupt:
        send_tg("🔴 Nado NLP Monitor stopped")
        sys.exit(0)
    except Exception as e:
        print("[!] " + str(e), flush=True)
        time.sleep(5)
