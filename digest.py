#!/usr/bin/env python3
"""
Owockibot Weekly Digest Generator
Generates a markdown + HTML email digest of owockibot weekly activity.
"""

import urllib.request
import json
import datetime
import os
import re

# ─── Config ──────────────────────────────────────────────────────────────────
BOUNTY_API = "https://www.owockibot.xyz/api/bounty-board"
BOUNTY_STATS_API = "https://www.owockibot.xyz/api/bounty-board/stats"
SAFE_ADDRESS = "0x26B7805Dd8aEc26DA55fc8e0c659cf6822b740Be"
SAFE_API = f"https://safe-transaction-base.safe.global/api/v1/safes/{SAFE_ADDRESS}"
TWITTER_BEARER = os.environ.get("TWITTER_BEARER_TOKEN", "")
TWITTER_USER = "owockibot"

def fetch_json(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "owockibot-digest/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())

def get_week_range():
    today = datetime.date.today()
    week_ago = today - datetime.timedelta(days=7)
    return week_ago, today

def fetch_bounty_data():
    bounties = fetch_json(BOUNTY_API)
    stats = fetch_json(BOUNTY_STATS_API)

    week_ago, today = get_week_range()
    week_ago_str = week_ago.isoformat()

    completed_this_week = []
    active_claimers = set()
    usdc_paid = 0

    for b in bounties:
        updated = b.get("updated_at", "")[:10]
        created = b.get("created_at", "")[:10]

        if b["status"] == "completed" and updated >= week_ago_str:
            completed_this_week.append(b)
            usdc_paid += b.get("reward_usdc", 0)
            if b.get("claimer_address"):
                active_claimers.add(b["claimer_address"])
        elif b["status"] in ("claimed", "submitted") and created >= week_ago_str:
            if b.get("claimer_address"):
                active_claimers.add(b["claimer_address"])

    return {
        "stats": stats,
        "completed_this_week": completed_this_week,
        "active_claimers": list(active_claimers),
        "usdc_paid_this_week": usdc_paid,
    }

def fetch_treasury():
    try:
        balances = fetch_json(f"{SAFE_API}/balances/")
        holdings = []
        for b in balances:
            if b["token"] is None:
                bal = int(b["balance"]) / 1e18
                if bal > 0.001:
                    holdings.append({"symbol": "ETH", "balance": f"{bal:.4f}"})
            else:
                decimals = b["token"]["decimals"]
                bal = int(b["balance"]) / (10 ** decimals)
                if bal > 0:
                    holdings.append({
                        "symbol": b["token"]["symbol"],
                        "balance": f"{bal:.2f}"
                    })
        return {"holdings": holdings[:8]}
    except Exception as e:
        return {"holdings": [], "error": str(e)}

def fetch_tweets():
    """Fetch recent tweets from @owockibot using Twitter API v2 Bearer token."""
    if not TWITTER_BEARER:
        return []
    try:
        url = (
            f"https://api.twitter.com/2/tweets/search/recent"
            f"?query=from:{TWITTER_USER}&tweet.fields=public_metrics,created_at&max_results=10"
        )
        data = fetch_json(url, headers={"Authorization": f"Bearer {TWITTER_BEARER}"})
        tweets = []
        for t in data.get("data", []):
            m = t.get("public_metrics", {})
            tweets.append({
                "id": t["id"],
                "text": t["text"][:120] + ("…" if len(t["text"]) > 120 else ""),
                "likes": m.get("like_count", 0),
                "retweets": m.get("retweet_count", 0),
                "created": t.get("created_at", "")[:10],
            })
        tweets.sort(key=lambda x: x["likes"], reverse=True)
        return tweets[:3]
    except Exception:
        return []

def generate_markdown(bounty_data, treasury, tweets, week_ago, today):
    lines = []
    lines.append("# 🌊 Owockibot Weekly Digest")
    lines.append(f"**Week of {week_ago} → {today}**\n")

    s = bounty_data["stats"]
    lines.append("## 📊 Platform Stats")
    lines.append(f"- **Total bounties:** {s['total']}")
    lines.append(f"- **Completed (all time):** {s['completed']}")
    lines.append(f"- **Total USDC paid (all time):** ${s['total_volume_usdc']:,}")
    lines.append(f"- **Open bounties:** {s['open']}\n")

    lines.append("## ✅ Completed This Week")
    if bounty_data["completed_this_week"]:
        lines.append(f"**{len(bounty_data['completed_this_week'])} bounties — ${bounty_data['usdc_paid_this_week']} USDC paid**\n")
        for b in bounty_data["completed_this_week"]:
            claimer = b.get("claimer_address", "")
            short = claimer[:6] + "…" + claimer[-4:] if claimer else "unknown"
            lines.append(f"- **{b['title']}** — ${b['reward_usdc']} USDC → {short}")
            if b.get("submission_url"):
                url = b["submission_url"]
                label = url[:60] + ("…" if len(url) > 60 else "")
                lines.append(f"  - 📎 [{label}]({url})")
    else:
        lines.append("_No bounties completed this week._")
    lines.append("")

    lines.append("## 👷 Active Builders This Week")
    if bounty_data["active_claimers"]:
        lines.append(f"**{len(bounty_data['active_claimers'])} unique wallets**\n")
        for addr in bounty_data["active_claimers"][:6]:
            short = addr[:6] + "…" + addr[-4:]
            lines.append(f"- [{short}](https://basescan.org/address/{addr})")
    else:
        lines.append("_No new activity this week._")
    lines.append("")

    lines.append("## 🏦 Treasury")
    lines.append(f"[Safe: {SAFE_ADDRESS[:10]}…](https://app.safe.global/base:{SAFE_ADDRESS})\n")
    if treasury.get("holdings"):
        for h in treasury["holdings"]:
            lines.append(f"- **{h['symbol']}:** {h['balance']}")
    else:
        lines.append("_Treasury data unavailable._")
    lines.append("")

    if tweets:
        lines.append("## 🐦 Top Tweets This Week")
        for t in tweets:
            lines.append(f"- [{t['text']}](https://x.com/{TWITTER_USER}/status/{t['id']}) — ❤️ {t['likes']} 🔄 {t['retweets']}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by [unleashedBelial](https://x.com/unleashedBelial) • {today}*")
    return "\n".join(lines)


def generate_html(bounty_data, treasury, tweets, week_ago, today):
    s = bounty_data["stats"]

    # ── Completed bounties rows ──
    completed_rows = ""
    for b in bounty_data["completed_this_week"]:
        claimer = b.get("claimer_address", "")
        short = (claimer[:6] + "…" + claimer[-4:]) if claimer else "unknown"
        link = b.get("submission_url", "")
        sub_html = f'<a href="{link}" class="link" target="_blank">📎 view</a>' if link else ""
        completed_rows += f"""
        <div class="bounty-row">
          <div class="bounty-title">{b['title']}</div>
          <div class="bounty-meta">
            <span class="tag green">${b['reward_usdc']} USDC</span>
            <span class="addr">{short}</span>
            {sub_html}
          </div>
        </div>"""

    if not completed_rows:
        completed_rows = '<p class="muted">No bounties completed this week.</p>'

    # ── Treasury rows ──
    treasury_rows = ""
    for h in treasury.get("holdings", []):
        treasury_rows += f'<div class="holding"><span class="symbol">{h["symbol"]}</span><span class="bal">{h["balance"]}</span></div>'
    if not treasury_rows:
        treasury_rows = '<p class="muted">Treasury data unavailable.</p>'

    # ── Builder rows ──
    builder_rows = ""
    for addr in bounty_data["active_claimers"][:6]:
        short = addr[:6] + "…" + addr[-4:]
        builder_rows += f'<a href="https://basescan.org/address/{addr}" class="builder-tag" target="_blank">{short}</a>'
    if not builder_rows:
        builder_rows = '<p class="muted">No activity this week.</p>'

    # ── Tweet rows ──
    tweet_section = ""
    if tweets:
        tweet_html = ""
        for t in tweets:
            tweet_html += f"""
        <div class="tweet-row">
          <a href="https://x.com/{TWITTER_USER}/status/{t['id']}" class="link" target="_blank">{t['text']}</a>
          <div class="tweet-meta"><span>❤️ {t['likes']}</span><span>🔄 {t['retweets']}</span><span class="muted">{t['created']}</span></div>
        </div>"""
        tweet_section = f"""
      <div class="section">
        <h2>🐦 Top Tweets This Week</h2>
        {tweet_html}
      </div>"""

    usdc_paid = bounty_data["usdc_paid_this_week"]
    n_completed = len(bounty_data["completed_this_week"])
    n_builders = len(bounty_data["active_claimers"])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🌊 Owockibot Weekly Digest — {today}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #080c10;
    color: #d4d8de;
    max-width: 680px;
    margin: 0 auto;
    padding: 32px 20px;
    line-height: 1.6;
  }}
  .header {{
    border-bottom: 2px solid #f4c542;
    padding-bottom: 16px;
    margin-bottom: 24px;
  }}
  .header h1 {{
    color: #f4c542;
    font-size: 26px;
    font-weight: 700;
    letter-spacing: -0.5px;
  }}
  .header .subtitle {{
    color: #666;
    font-size: 13px;
    margin-top: 4px;
  }}
  .stats-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 28px;
  }}
  .stat-card {{
    background: #0f151c;
    border: 1px solid #1e2a38;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
  }}
  .stat-card .value {{
    font-size: 28px;
    font-weight: 700;
    color: #f4c542;
    display: block;
  }}
  .stat-card .label {{
    font-size: 11px;
    color: #556;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 4px;
  }}
  .section {{
    margin-bottom: 28px;
  }}
  h2 {{
    color: #f4c542;
    font-size: 15px;
    font-weight: 600;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .bounty-row {{
    background: #0f151c;
    border: 1px solid #1a2330;
    border-radius: 6px;
    padding: 12px 14px;
    margin-bottom: 8px;
  }}
  .bounty-title {{
    font-size: 14px;
    color: #e0e4ea;
    margin-bottom: 6px;
    font-weight: 500;
  }}
  .bounty-meta {{
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .tag {{
    font-size: 11px;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
  }}
  .tag.green {{
    background: #0d2e1a;
    color: #4ade80;
    border: 1px solid #14532d;
  }}
  .addr {{
    font-family: monospace;
    font-size: 11px;
    color: #556;
  }}
  .link {{
    color: #f4c542;
    text-decoration: none;
    font-size: 12px;
  }}
  .link:hover {{ text-decoration: underline; }}
  .treasury-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 8px;
  }}
  .holding {{
    background: #0f151c;
    border: 1px solid #1a2330;
    border-radius: 6px;
    padding: 10px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .symbol {{
    font-size: 12px;
    font-weight: 600;
    color: #f4c542;
  }}
  .bal {{
    font-size: 12px;
    color: #889;
    font-family: monospace;
  }}
  .builders-wrap {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .builder-tag {{
    background: #0f151c;
    border: 1px solid #1e2a38;
    border-radius: 4px;
    padding: 4px 10px;
    font-family: monospace;
    font-size: 12px;
    color: #aab;
    text-decoration: none;
  }}
  .builder-tag:hover {{ border-color: #f4c542; color: #f4c542; }}
  .tweet-row {{
    padding: 12px 0;
    border-bottom: 1px solid #141c26;
  }}
  .tweet-row:last-child {{ border-bottom: none; }}
  .tweet-meta {{
    display: flex;
    gap: 12px;
    margin-top: 4px;
    font-size: 12px;
    color: #556;
  }}
  .muted {{ color: #445; font-size: 13px; }}
  .footer {{
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid #1a2330;
    font-size: 12px;
    color: #445;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }}
  .footer a {{ color: #f4c54280; text-decoration: none; }}
  .footer a:hover {{ color: #f4c542; }}
</style>
</head>
<body>

<div class="header">
  <h1>🌊 Owockibot Weekly Digest</h1>
  <div class="subtitle">Week of {week_ago} → {today}</div>
</div>

<div class="stats-grid">
  <div class="stat-card">
    <span class="value">{n_completed}</span>
    <div class="label">Bounties Completed</div>
  </div>
  <div class="stat-card">
    <span class="value">${usdc_paid}</span>
    <div class="label">USDC Paid Out</div>
  </div>
  <div class="stat-card">
    <span class="value">{n_builders}</span>
    <div class="label">Active Builders</div>
  </div>
</div>

<div class="section">
  <h2>✅ Completed This Week</h2>
  {completed_rows}
</div>

<div class="section">
  <h2>👷 Active Builders</h2>
  <div class="builders-wrap">
    {builder_rows}
  </div>
</div>

<div class="section">
  <h2>🏦 Treasury Holdings
    <a href="https://app.safe.global/base:{SAFE_ADDRESS}" class="link" target="_blank" style="font-weight:400;font-size:12px;margin-left:4px">↗ Safe</a>
  </h2>
  <div class="treasury-grid">
    {treasury_rows}
  </div>
</div>

{tweet_section}

<div class="footer">
  <span>Generated by <a href="https://x.com/unleashedBelial">@unleashedBelial</a></span>
  <span>{today}</span>
</div>

</body>
</html>"""


def main():
    week_ago, today = get_week_range()
    print(f"🌊 Generating Owockibot Weekly Digest for {week_ago} → {today}...")

    print("  Fetching bounty data...")
    bounty_data = fetch_bounty_data()

    print("  Fetching treasury data...")
    treasury = fetch_treasury()

    print("  Fetching tweets...")
    tweets = fetch_tweets()
    if not tweets:
        print("  ⚠️  No tweets (set TWITTER_BEARER_TOKEN to enable)")

    print(f"  ✅ Completed this week: {len(bounty_data['completed_this_week'])}")
    print(f"  💰 USDC paid: ${bounty_data['usdc_paid_this_week']}")
    print(f"  👷 Active builders: {len(bounty_data['active_claimers'])}")
    print(f"  🏦 Treasury holdings: {len(treasury.get('holdings', []))}")

    md = generate_markdown(bounty_data, treasury, tweets, week_ago, today)
    html = generate_html(bounty_data, treasury, tweets, week_ago, today)

    os.makedirs("output", exist_ok=True)
    with open(f"output/digest-{today}.md", "w") as f:
        f.write(md)
    with open(f"output/digest-{today}.html", "w") as f:
        f.write(html)

    print(f"\n✅ Digest generated:")
    print(f"   📄 output/digest-{today}.md")
    print(f"   🌐 output/digest-{today}.html")


if __name__ == "__main__":
    main()
