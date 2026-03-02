#!/usr/bin/env python3
"""
Owockibot Weekly Digest Generator
Generates a markdown + HTML email digest of owockibot weekly activity.
"""

import urllib.request
import json
import datetime
import os
import sys

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
    
    # Filter bounties updated this week
    completed_this_week = []
    new_claimers = set()
    usdc_paid = 0
    
    for b in bounties:
        updated = b.get("updated_at", "")[:10]
        created = b.get("created_at", "")[:10]
        
        if b["status"] == "completed" and updated >= week_ago_str:
            completed_this_week.append(b)
            usdc_paid += b.get("reward_usdc", 0)
            if b.get("claimer_address"):
                new_claimers.add(b["claimer_address"])
        elif b["status"] == "claimed" and created >= week_ago_str:
            if b.get("claimer_address"):
                new_claimers.add(b["claimer_address"])
    
    return {
        "stats": stats,
        "completed_this_week": completed_this_week,
        "new_claimers": list(new_claimers),
        "usdc_paid_this_week": usdc_paid,
    }

def fetch_treasury():
    try:
        balances = fetch_json(f"{SAFE_API}/balances/")
        txs = fetch_json(f"{SAFE_API}/multisig-transactions/?limit=5")
        
        holdings = []
        for b in balances:
            if b["token"] is None:
                bal = int(b["balance"]) / 1e18
                if bal > 0.001:
                    holdings.append({"symbol": "ETH", "balance": f"{bal:.4f}"})
            else:
                bal = int(b["balance"]) / (10 ** b["token"]["decimals"])
                if bal > 0:
                    holdings.append({
                        "symbol": b["token"]["symbol"],
                        "balance": f"{bal:.2f}"
                    })
        
        recent_txs = []
        for tx in txs.get("results", [])[:3]:
            recent_txs.append({
                "date": tx.get("submissionDate", "")[:10],
                "hash": tx.get("safeTxHash", "")[:10] + "...",
                "value": str(int(tx.get("value", "0")) / 1e18) + " ETH"
            })
        
        return {"holdings": holdings[:8], "recent_txs": recent_txs}
    except Exception as e:
        return {"holdings": [], "recent_txs": [], "error": str(e)}

def fetch_tweets():
    """Fetch recent tweets from @owockibot using Twitter API v2."""
    if not TWITTER_BEARER:
        return []
    try:
        url = f"https://api.twitter.com/2/tweets/search/recent?query=from:{TWITTER_USER}&tweet.fields=public_metrics,created_at&max_results=10"
        data = fetch_json(url, headers={"Authorization": f"Bearer {TWITTER_BEARER}"})
        tweets = []
        for t in data.get("data", []):
            m = t.get("public_metrics", {})
            tweets.append({
                "id": t["id"],
                "text": t["text"][:100] + ("..." if len(t["text"]) > 100 else ""),
                "likes": m.get("like_count", 0),
                "retweets": m.get("retweet_count", 0),
                "created": t.get("created_at", "")[:10]
            })
        # Sort by likes
        tweets.sort(key=lambda x: x["likes"], reverse=True)
        return tweets[:3]
    except Exception as e:
        return []

def generate_markdown(bounty_data, treasury, tweets, week_ago, today):
    lines = []
    lines.append(f"# 🌊 Owockibot Weekly Digest")
    lines.append(f"**Week of {week_ago} → {today}**\n")
    
    # Stats summary
    s = bounty_data["stats"]
    lines.append("## 📊 Platform Stats")
    lines.append(f"- **Total bounties:** {s['total']}")
    lines.append(f"- **Completed (all time):** {s['completed']}")
    lines.append(f"- **Total USDC paid:** ${s['total_volume_usdc']:,}")
    lines.append(f"- **Open bounties:** {s['open']}\n")
    
    # This week
    lines.append("## ✅ Completed This Week")
    if bounty_data["completed_this_week"]:
        lines.append(f"**{len(bounty_data['completed_this_week'])} bounties completed — ${bounty_data['usdc_paid_this_week']} USDC paid**\n")
        for b in bounty_data["completed_this_week"]:
            claimer = b.get("claimer_address", "")
            claimer_short = claimer[:6] + "..." + claimer[-4:] if claimer else "unknown"
            lines.append(f"- **{b['title']}** — ${b['reward_usdc']} USDC → {claimer_short}")
            if b.get("submission_url"):
                lines.append(f"  - 📎 [{b['submission_url'][:50]}]({b['submission_url']})")
    else:
        lines.append("_No bounties completed this week._")
    lines.append("")
    
    # New builders
    lines.append("## 👷 New Builders This Week")
    if bounty_data["new_claimers"]:
        lines.append(f"**{len(bounty_data['new_claimers'])} unique wallets active**\n")
        for addr in bounty_data["new_claimers"][:5]:
            short = addr[:6] + "..." + addr[-4:]
            lines.append(f"- [{short}](https://basescan.org/address/{addr})")
    else:
        lines.append("_No new builders this week._")
    lines.append("")
    
    # Treasury
    lines.append("## 🏦 Treasury")
    lines.append(f"[Safe: {SAFE_ADDRESS[:10]}...](https://app.safe.global/base:{SAFE_ADDRESS})\n")
    if treasury["holdings"]:
        for h in treasury["holdings"]:
            lines.append(f"- **{h['symbol']}:** {h['balance']}")
    else:
        lines.append("_Treasury data unavailable._")
    lines.append("")
    
    # Tweets
    if tweets:
        lines.append("## 🐦 Top Tweets This Week")
        for t in tweets:
            lines.append(f"- [{t['text']}](https://x.com/{TWITTER_USER}/status/{t['id']}) — ❤️ {t['likes']} 🔄 {t['retweets']}")
        lines.append("")
    
    lines.append("---")
    lines.append(f"*Generated by [unleashedBelial](https://x.com/unleashedBelial) • {today}*")
    
    return "\n".join(lines)

def generate_html(markdown_text, week_ago, today):
    import re
    
    # Convert markdown to basic HTML
    html = markdown_text
    # Headers
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    # Bold
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    # Italic
    html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)
    # Links
    html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2" style="color:#f4c542">\1</a>', html)
    # List items
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
    # Paragraphs
    lines = html.split('\n')
    result = []
    in_list = False
    for line in lines:
        if line.startswith('<li>'):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(line)
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            if line.strip() and not line.startswith('<h') and not line.startswith('<hr'):
                if not line.startswith('<'):
                    result.append(f'<p>{line}</p>')
                else:
                    result.append(line)
            elif line == '---':
                result.append('<hr style="border-color:#333">')
            elif not line.strip():
                pass
    if in_list:
        result.append('</ul>')
    
    body = '\n'.join(result)
    
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Owockibot Weekly Digest — {today}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; background: #0a0a0a; color: #e0e0e0; max-width: 640px; margin: 0 auto; padding: 24px; }}
  h1 {{ color: #f4c542; font-size: 28px; border-bottom: 2px solid #f4c542; padding-bottom: 8px; }}
  h2 {{ color: #f4c542; font-size: 18px; margin-top: 28px; }}
  p {{ line-height: 1.6; color: #ccc; }}
  ul {{ padding-left: 20px; }}
  li {{ margin: 6px 0; color: #ccc; }}
  strong {{ color: #fff; }}
  a {{ color: #f4c542; }}
  hr {{ border: none; border-top: 1px solid #333; margin: 24px 0; }}
  em {{ color: #888; font-style: normal; }}
  .footer {{ color: #555; font-size: 12px; text-align: center; margin-top: 32px; }}
</style>
</head>
<body>
{body}
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
    
    print(f"  ✅ Completed this week: {len(bounty_data['completed_this_week'])}")
    print(f"  💰 USDC paid: ${bounty_data['usdc_paid_this_week']}")
    print(f"  👷 New builders: {len(bounty_data['new_claimers'])}")
    print(f"  🏦 Treasury holdings: {len(treasury['holdings'])}")
    
    md = generate_markdown(bounty_data, treasury, tweets, week_ago, today)
    html = generate_html(md, week_ago, today)
    
    # Save outputs
    os.makedirs("output", exist_ok=True)
    with open(f"output/digest-{today}.md", "w") as f:
        f.write(md)
    with open(f"output/digest-{today}.html", "w") as f:
        f.write(html)
    
    print(f"\n✅ Digest generated:")
    print(f"   📄 output/digest-{today}.md")
    print(f"   🌐 output/digest-{today}.html")
    print(f"\n--- PREVIEW ---")
    print(md[:800])

if __name__ == "__main__":
    main()
