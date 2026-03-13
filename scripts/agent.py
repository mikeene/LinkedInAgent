"""
Tech4Dev LinkedIn Executive Post Agent v2
- Scrapes REAL Tech4Dev LinkedIn posts via Apify (bypasses LinkedIn's bot block)
- Generates executive post prompts via Groq (free LLM)
- Sends email via Resend
"""

import os
import json
import time
import requests
from datetime import datetime

# ── Config from environment variables ──────────────────────────────────────
GROQ_API_KEY    = os.environ["GROQ_API_KEY"]
RESEND_API_KEY  = os.environ["RESEND_API_KEY"]
SENDER_EMAIL    = os.environ["SENDER_EMAIL"]
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]
APIFY_API_TOKEN = os.environ["APIFY_API_TOKEN"]

TECH4DEV_LINKEDIN_URL = "https://www.linkedin.com/company/tech4dev/"

# Apify actor ID for LinkedIn Company Posts scraper
APIFY_ACTOR_ID = "2SyF0bVxmgGr8IVCZ"


# ── Step 1: Scrape Tech4Dev LinkedIn posts via Apify ──────────────────────
def scrape_linkedin_posts() -> list[dict]:
    """
    Uses Apify's LinkedIn Company Posts scraper actor.
    This works because Apify uses residential proxies that bypass
    LinkedIn's bot detection — unlike a plain requests.get() which
    always gets blocked and returns a login wall.
    """
    print("🔍 Starting Apify LinkedIn scrape for Tech4Dev...")

    # ── 1a. Start the Apify actor run ──────────────────────────────────────
    run_response = requests.post(
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs",
        params={"token": APIFY_API_TOKEN},
        json={
            "startUrls": [{"url": TECH4DEV_LINKEDIN_URL}],
            "maxPosts": 8,
            "proxy": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"]
            }
        },
        timeout=30,
    )
    run_response.raise_for_status()
    run_data      = run_response.json()["data"]
    run_id        = run_data["id"]
    dataset_id    = run_data["defaultDatasetId"]
    print(f"   Apify run started → Run ID: {run_id}")

    # ── 1b. Poll until the run finishes (max 4 minutes) ────────────────────
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}"
    for attempt in range(48):          # 48 × 5 s = 4 minutes max
        time.sleep(5)
        status_resp = requests.get(
            status_url, params={"token": APIFY_API_TOKEN}, timeout=15
        )
        status = status_resp.json()["data"]["status"]
        print(f"   [{attempt+1}/48] Status: {status}")
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify actor failed: {status}")
    else:
        raise RuntimeError("Apify timed out after 4 minutes.")

    # ── 1c. Fetch results ──────────────────────────────────────────────────
    items_resp = requests.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        params={"token": APIFY_API_TOKEN, "format": "json", "clean": "true"},
        timeout=30,
    )
    items_resp.raise_for_status()
    items = items_resp.json()
    print(f"✅ Apify returned {len(items)} raw items.")

    # ── 1d. Normalise into clean post dicts ───────────────────────────────
    posts = []
    for item in items:
        text = (
            item.get("text") or item.get("description")
            or item.get("content") or ""
        ).strip()
        if len(text) < 60:
            continue
        posts.append({
            "text":     text[:1500],
            "url":      item.get("url") or item.get("postUrl") or "",
            "date":     item.get("date") or item.get("postedAt") or "",
            "likes":    item.get("likes") or item.get("likesCount") or 0,
            "comments": item.get("comments") or item.get("commentsCount") or 0,
            "source":   "apify_live",
        })

    if not posts:
        raise RuntimeError(
            "Apify ran successfully but found no post text. "
            "Check the actor run in your Apify console dashboard."
        )

    print(f"   Extracted {len(posts)} usable posts.")
    return posts[:8]


# ── Step 2: Generate executive post prompts via Groq ──────────────────────
def generate_post_prompts(posts: list[dict]) -> str:
    """Feed REAL scraped posts to LLaMA so prompts are never generic."""

    # Build a rich posts block so the LLM has real content to work with
    posts_block = ""
    for i, p in enumerate(posts[:6], 1):
        date_str = f" · {p['date']}" if p["date"] else ""
        eng_str  = f" · 👍{p['likes']} 💬{p['comments']}" if p["likes"] else ""
        posts_block += f"[Post {i}{date_str}{eng_str}]\n{p['text']}\n\n"

    system_prompt = """You are a ghostwriter for a senior executive at Tech4Dev,
a leading African tech NGO focused on digital skills, inclusion, and empowerment.

Your job is to write 3 compelling LinkedIn post PROMPTS (not full posts) that the 
executive can use as a starting point this week.

CRITICAL RULE: Every prompt MUST reference something specific from the actual posts 
provided — a specific program, event, milestone, or theme. NEVER give generic prompts.

For each of the 3 prompts, provide:
- HEADLINE/HOOK: The exact opening line
- TECH4DEV CONNECTION: Which specific post/activity this is based on (quote a detail)
- KEY POINTS: 2-3 bullets the exec should cover
- PERSONAL ANGLE: A story or reflection the exec can make their own
- CALL TO ACTION: Closing question or prompt for engagement
- HASHTAGS: 4-5 relevant tags

Format clearly with "PROMPT 1 —", "PROMPT 2 —", "PROMPT 3 —" headers.
Mix the themes: one on impact/mission, one on people/team, one on the exec's personal journey."""

    user_message = f"""Today is {datetime.now().strftime('%A, %B %d %Y')}.

Here are the {len(posts[:6])} most recent posts published by Tech4Dev on LinkedIn:

{posts_block}
Study these carefully. Then write 3 executive LinkedIn post prompts that react to, 
expand on, or add a personal leadership angle to what Tech4Dev is currently publishing.
Every prompt must tie back to something SPECIFIC in the posts above."""

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.3-70b-versatile",   # Upgraded from 8b to 70b for quality
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_message},
            ],
            "temperature": 0.85,
            "max_tokens": 2000,
        },
        timeout=45,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


# ── Step 3: Send email via Resend ──────────────────────────────────────────
def send_email(prompts: str, posts: list[dict]):
    today = datetime.now().strftime("%A, %B %d %Y")
    subject = f"📝 Your LinkedIn Post Prompts — {today} | Live Tech4Dev Data"

    # Format the prompts: bold the section headers
    prompts_html = (
        prompts
        .replace("\n", "<br>")
        .replace("PROMPT 1 —", "<br><strong style='color:#e94560;font-size:16px'>PROMPT 1 —</strong>")
        .replace("PROMPT 2 —", "<br><br><strong style='color:#e94560;font-size:16px'>PROMPT 2 —</strong>")
        .replace("PROMPT 3 —", "<br><br><strong style='color:#e94560;font-size:16px'>PROMPT 3 —</strong>")
        .replace("HEADLINE/HOOK:",      "<br><strong>🪝 HEADLINE/HOOK:</strong>")
        .replace("TECH4DEV CONNECTION:","<br><strong>🔗 TECH4DEV CONNECTION:</strong>")
        .replace("KEY POINTS:",         "<br><strong>📌 KEY POINTS:</strong>")
        .replace("PERSONAL ANGLE:",     "<br><strong>💡 PERSONAL ANGLE:</strong>")
        .replace("CALL TO ACTION:",     "<br><strong>📣 CALL TO ACTION:</strong>")
        .replace("HASHTAGS:",           "<br><strong>🏷 HASHTAGS:</strong>")
    )

    # Show a preview of the real posts that were used
    posts_preview = "".join(
        f"""<li style='margin-bottom:10px;color:#555;font-size:13px;'>
              <span style='color:#0A66C2;font-weight:600;'>Post {i}</span>
              {"· " + p['date'] if p['date'] else ""}
              {"· 👍" + str(p['likes']) if p['likes'] else ""}
              <br>{p['text'][:180]}…
           </li>"""
        for i, p in enumerate(posts[:4], 1)
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#333;background:#f3f3f3">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:30px;border-radius:12px;margin-bottom:20px;text-align:center">
    <h1 style="color:#e94560;margin:0;font-size:22px">Tech4Dev LinkedIn Agent</h1>
    <p style="color:#aaa;margin:8px 0 0;font-size:14px">Executive Post Prompts — {today}</p>
  </div>

  <!-- Live data badge -->
  <div style="background:#E3F2FD;border-left:4px solid #0A66C2;padding:14px 18px;border-radius:6px;margin-bottom:20px;font-size:13px;color:#1565C0">
    <strong>✅ Based on {len(posts)} LIVE posts</strong> scraped from Tech4Dev's LinkedIn page today — 
    not templates. Every prompt connects to something they actually published.
  </div>

  <!-- Prompts -->
  <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:26px;margin-bottom:20px">
    <h2 style="color:#1a1a2e;font-size:18px;margin-top:0;border-bottom:2px solid #e94560;padding-bottom:10px">
      Your 3 Post Prompts This Week
    </h2>
    <div style="font-size:14px;line-height:1.8;color:#333">
      {prompts_html}
    </div>
  </div>

  <!-- Source posts used -->
  <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:20px;margin-bottom:20px">
    <h2 style="color:#1a1a2e;font-size:15px;margin-top:0">
      📡 Tech4Dev Posts Used as Source
    </h2>
    <ul style="padding-left:16px;margin:0">
      {posts_preview}
    </ul>
    <a href="{TECH4DEV_LINKEDIN_URL}" style="font-size:12px;color:#0A66C2;display:block;margin-top:12px">
      View Tech4Dev on LinkedIn →
    </a>
  </div>

  <!-- Tips -->
  <div style="background:#fff8e1;border-radius:8px;padding:16px;font-size:13px;color:#555">
    <strong>💡 Tips for posting:</strong><br>
    - Add a personal story to make each prompt your own<br>
    - Tuesday–Thursday gets the best LinkedIn engagement<br>
    - End with a question to spark comments<br>
    - Keep it under 1,300 characters for best reach
  </div>

  <p style="text-align:center;font-size:11px;color:#bbb;margin-top:20px">
    Tech4Dev LinkedIn Agent · Runs Monday, Wednesday & Friday
  </p>
</body>
</html>"""

    print(f"DEBUG sender: '***'")
    print(f"DEBUG recipient: '***'")

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "from":    SENDER_EMAIL,
            "to":      [RECIPIENT_EMAIL],
            "subject": subject,
            "html":    html_body,
        },
        timeout=30,
    )

    if response.status_code in (200, 201):
        print(f"✅ Email sent to {RECIPIENT_EMAIL}")
    else:
        print(f"❌ Resend error: {response.status_code} — {response.text}")
        response.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Tech4Dev LinkedIn Agent starting...")

    print("\n🔍 Scraping LinkedIn posts via Apify...")
    posts = scrape_linkedin_posts()
    print(f"   Found {len(posts)} real posts.\n")

    print("🤖 Generating post prompts with Groq LLaMA 3.3 70B...")
    prompts = generate_post_prompts(posts)
    print("   Prompts generated.\n")

    print("📧 Sending email...")
    send_email(prompts, posts)

    print("\n✅ Done!")
