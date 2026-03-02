# 🌊 Owockibot Weekly Digest Generator

A Python script that generates a weekly markdown + HTML digest of [owockibot.xyz](https://owockibot.xyz) activity.

**Live demo:** [unleashedbelial.github.io/owockibot-digest](https://unleashedbelial.github.io/owockibot-digest/)

---

## What it pulls

| Source | Data |
|--------|------|
| [Bounty Board API](https://www.owockibot.xyz/api/bounty-board) | Completed bounties, USDC paid, active builders |
| [Safe API](https://safe-transaction-base.safe.global) | Treasury holdings for `0x26B7805D...` on Base |
| [Twitter API v2](https://developer.twitter.com/en/docs/twitter-api) | Top tweets from @owockibot *(optional — requires Bearer token)* |

---

## Output

- `output/digest-YYYY-MM-DD.md` — Markdown digest
- `output/digest-YYYY-MM-DD.html` — Styled HTML email template (dark theme, gold accents)

---

## Usage

```bash
# Basic (no Twitter)
python3 digest.py

# With Twitter API
export TWITTER_BEARER_TOKEN=your_bearer_token_here
python3 digest.py
```

### Getting a Twitter Bearer Token

The script fetches tweets from @owockibot using **Twitter API v2** (read-only, no OAuth needed — just a Bearer token from the account that owns the @owockibot developer app).

1. Go to [developer.twitter.com](https://developer.twitter.com)
2. Create a project/app (free tier works)
3. Copy the **Bearer Token** from the "Keys and tokens" tab
4. Set it as `TWITTER_BEARER_TOKEN` env var before running

> **Note:** The Bearer token must belong to the app associated with the @owockibot account, or any app with access to the Twitter API v2 search endpoint. Without it, the digest still generates fully — the tweets section is simply omitted.

---

## Requirements

- Python 3.8+
- No external dependencies (stdlib only)

---

## Schedule

Run weekly via cron to auto-publish:

```cron
0 9 * * MON cd /path/to/owockibot-digest && python3 digest.py
```

---

Built for the [Owockibot Weekly Digest Generator bounty](https://www.owockibot.xyz/bounty) by [@unleashedBelial](https://x.com/unleashedBelial)
