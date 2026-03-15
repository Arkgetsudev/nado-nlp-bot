# Nado NLP Vault Monitor 🔔

Monitors the Nado NLP vault for withdrawals and sends Telegram alerts.

## Deploy to Railway (2 min)

1. Push this repo to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add these **Variables** in Railway dashboard:

| Variable | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TELEGRAM_CHAT_IDS` | Comma-separated chat IDs: `123456,789012,-100123456` |
| `POLL_INTERVAL` | `15` (seconds between checks) |
| `MIN_WITHDRAWAL` | `0` (min USDT0 to alert, 0 = all) |

4. Deploy. Done.

## Add to more Telegram groups/channels

1. Add your bot to the group or channel
2. Get the chat ID (it's negative for groups, like `-1001234567890`)
3. Add it to `TELEGRAM_CHAT_IDS` in Railway, comma-separated
4. Railway auto-redeploys

## Alerts look like

> 🔔 **NLP Withdrawal Detected**
> 💰 **-5,000.00 USDT0**
> 📉 4,000,000.00 → 3,995,000.00 USDT0
> 🕐 14:32:10 UTC
> 👉 [Deposit now](https://app.nado.xyz/vault)
