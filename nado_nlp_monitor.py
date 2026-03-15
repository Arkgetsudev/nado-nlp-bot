#!/usr/bin/env python3
"""
Nado NLP Vault Withdrawal Monitor
----------------------------------
Monitors the Nado NLP vault for withdrawals and sends Telegram alerts.
Designed to run on Railway.app with environment variables.

Env vars:
  TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
  TELEGRAM_CHAT_IDS   — Comma-separated chat IDs (users, groups, channels)
  POLL_INTERVAL        — Seconds between checks (default: 15)
  MIN_WITHDRAWAL       — Min USDT0 withdrawal to alert (default: 0)
"""

import requests
import time
import json
import sys
import os
from datetime import datetime, timezone

# ============================================================
# CONFIG FROM ENV
# ============================================================

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_IDS = [
    cid.strip()
    for cid in os.environ.get("TELEGRAM_CHAT_IDS", "").split(",")
    if cid.strip()
]
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "15"))
MIN_WITHDRAWAL = float(os.environ.get("MIN_WITHDRAWAL", "0"))

NADO_API = "https://gateway.prod.nado.xyz/v1/query"

# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message: str):
    """Send message to ALL configured Telegram chats."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        print(f"[TG] No token/chats configured. Message: {message[:100]}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            resp = requests.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }, timeout=10)
            if resp.status_code == 200:
                print(f"[TG] Sent to {chat_id}")
            else:
                print(f"[TG] Error {chat_id}: {resp.status_code} - {resp.text[:100]}")
        except Exception as e:
            print(f"[TG] Failed {chat_id}: {e}")

# ============================================================
# NADO API
# ============================================================

def fetch_nlp_info() -> dict | None:
    """Fetch NLP pool info from Nado."""
    try:
        resp = requests.get(
            f"{NADO_API}?type=nlp_pool_info",
            headers={"Accept-Encoding": "gzip, deflate"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        print(f"[API] Error: {resp.status_code}")
        return None
    except Exception as e:
        print(f"[API] Failed: {e}")
        return None


def get_vault_total(data: dict) -> float | None:
    """
    Extract total vault deposits from API response.
    Tries multiple possible response formats.
    Returns value in USDT0.
    """
    try:
        d = data
        if "data" in d:
            d = d["data"]
        if "result" in d:
            d = d["result"]
        if isinstance(d, list) and len(d) > 0:
            d = d[0]

        # x18 encoded fields (divide by 1e18)
        for key in ["total_quote", "total_deposits", "total_lp_deposits",
                     "total_assets", "total_quote_amount", "pool_total"]:
            if key in d:
                val = float(d[key])
                if val > 1e12:  # likely x18
                    return val / 1e18
                elif val > 1e4:  # likely x6
                    return val / 1e6
                return val

        # x6 encoded
        for key in ["tvl"]:
            if key in d:
                return float(d[key]) / 1e6

        # raw value
        for key in ["capacity", "total"]:
            if key in d:
                return float(d[key])

        return None
    except Exception as e:
        print(f"[PARSE] Error: {e}")
        return None

# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 50)
    print("  NADO NLP VAULT MONITOR")
    print("=" * 50)

    # Validate config
    if not TELEGRAM_BOT_TOKEN:
        print("[!] TELEGRAM_BOT_TOKEN not set!")
        print("    Set it in Railway Variables or as env var.")
        sys.exit(1)

    if not TELEGRAM_CHAT_IDS:
        print("[!] TELEGRAM_CHAT_IDS not set!")
        print("    Set comma-separated IDs in Railway Variables.")
        sys.exit(1)

    print(f"  Chats:    {TELEGRAM_CHAT_IDS}")
    print(f"  Polling:  {POLL_INTERVAL}s")
    print(f"  Min alert: {MIN_WITHDRAWAL} USDT0")
    print("=" * 50)

    # Initial state
    print("[*] Fetching initial vault state...")
    data = fetch_nlp_info()
    if data:
        print(f"[+] Raw: {json.dumps(data)[:500]}")

    prev = get_vault_total(data) if data else None
    if prev is not None:
        print(f"[+] Vault total: {prev:,.2f} USDT0")
        send_telegram(
            f"🟢 <b>Nado NLP Monitor Online</b>\n\n"
            f"Vault: <b>{prev:,.2f} USDT0</b>\n"
            f"Polling every {POLL_INTERVAL}s"
        )
    else:
        print("[!] Could not parse vault total. Check raw response above.")
        send_telegram("🟡 <b>Nado NLP Monitor Online</b>\n\nCould not read vault total yet. Monitoring...")

    print(f"\n[*] Monitoring...\n")

    errors = 0
    withdrawals = 0

    while True:
        try:
            time.sleep(POLL_INTERVAL)

            data = fetch_nlp_info()
            if not data:
                errors += 1
                if errors == 10:
                    send_telegram("🔴 <b>Nado API unreachable</b> (10+ failed polls)")
                continue

            errors = 0
            current = get_vault_total(data)
            if current is None:
                continue

            if prev is not None:
                diff = current - prev

                if diff < 0 and abs(diff) >= MIN_WITHDRAWAL:
                    withdrawals += 1
                    amt = abs(diff)
                    now = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

                    print(f"[🔔 #{withdrawals}] -{amt:,.2f} USDT0 | {prev:,.2f} → {current:,.2f}")

                    send_telegram(
                        f"🔔 <b>NLP Withdrawal Detected</b>\n\n"
                        f"💰 <b>-{amt:,.2f} USDT0</b>\n"
                        f"📉 {prev:,.2f} → {current:,.2f} USDT0\n"
                        f"🕐 {now}\n\n"
                        f"👉 <a href='https://app.nado.xyz/vault'>Deposit now</a>"
                    )

                elif diff > 0:
                    t = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    print(f"  [{t}] +{diff:,.2f} → {current:,.2f}")

            prev = current

        except KeyboardInterrupt:
            send_telegram("🔴 <b>Nado NLP Monitor stopped</b>")
            sys.exit(0)
        except Exception as e:
            print(f"[!] Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
