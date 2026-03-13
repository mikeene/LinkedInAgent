"""
LinkedIn Post Prompt Bot — Emenike Madukairo
Uses Apify to scrape real Tech4Dev LinkedIn posts, then generates
tailored prompts with Groq (LLaMA 3.3 70B, free tier).
Runs Monday & Wednesday via GitHub Actions.
"""

import os
import json
import time
import smtplib
import urllib.request
import urllib.error
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


# ── Constants ────────────────────────────────────────────────────────────────

TECH4DEV_LINKEDIN_URL = "https://www.linkedin.com/company/tech4dev/"

AUTHOR_PROFILE = {
    "name": "Emenike Madukairo",
    "role": "Business Operations & Strategy professional",
    "audience": "Nigerian tech professionals, young entrepreneurs, career starters",
    "tone": "Thoughtful, story-driven, analytical but relatable",
}

# ── Apify Scraper ────────────────────────────────────────────────────────────

def scrape_tech4dev_posts() -> list[dict]:
    """
    Calls Apify's LinkedIn Company Posts scraper actor.
    Actor: apify/linkedin-company-posts-scraper
    Returns a list of post dicts with keys: text, url, date, likes, comments
    """
    api_token = os.environ.get("APIFY_API_TOKEN")
    if not api_token:
        raise ValueError("APIFY_API_TOKEN secret is not set in GitHub.")

    actor_id = "2SyF0bVxmgGr8IVCZ"   # apify/linkedin-company-posts-scraper

    print("🔍 Starting Apify scrape of Tech4Dev LinkedIn page...")

    # ── Step 1: Start the actor run ──────────────────────────────────────────
    run_payload = json.dumps({
        "startUrls": [{"url": TECH4DEV_LINKEDIN_URL}],
        "maxPosts": 8,          # Grab the 8 most recent posts
        "proxy": {
            "useApifyProxy": True,
            "apifyProxyGroups": ["RESIDENTIAL"]   # Required to bypass LinkedIn
        }
    }).encode("utf-8")

    start_req = urllib.request.Request(
        f"https://api.apify.com/v2/acts/{actor_id}/runs?token={api_token}",
        data=run_payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(start_req, timeout=30) as resp:
        run_data = json.loads(resp.read())

    run_id = run_data["data"]["id"]
    dataset_id = run_data["data"]["defaultDatasetId"]
    print(f"   Apify run started. Run ID: {run_id}")

    # ── Step 2: Poll until the run finishes (max 3 minutes) ──────────────────
    status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={api_token}"
    for attempt in range(36):   # 36 × 5s = 3 minutes max
        time.sleep(5)
        with urllib.request.urlopen(status_url, timeout=15) as resp:
            status_data = json.loads(resp.read())
        status = status_data["data"]["status"]
        print(f"   [{attempt+1}/36] Run status: {status}")
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify actor run failed with status: {status}")
    else:
        raise RuntimeError("Apify actor timed out after 3 minutes.")

    # ── Step 3: Fetch results from the dataset ───────────────────────────────
    dataset_url = (
        f"https://api.apify.com/v2/datasets/{dataset_id}/items"
        f"?token={api_token}&format=json&clean=true"
    )
    with urllib.request.urlopen(dataset_url, timeout=30) as resp:
        items = json.loads(resp.read())

    print(f"✅ Apify returned {len(items)} posts from Tech4Dev.")

    # ── Step 4: Normalise into a clean list ──────────────────────────────────
    posts = []
    for item in items:
        text = (
            item.get("text")
            or item.get("description")
            or item.get("content")
            or ""
        ).strip()
        if len(text) < 40:          # Skip near-empty items
            continue
        posts.append({
            "text":     text[:1200],   # Cap at 1 200 chars to stay under token limit
            "url":      item.get("url") or item.get("postUrl") or "",
            "date":     item.get("date") or item.get("postedAt") or "",
            "likes":    item.get("likes") or item.get("likesCount") or 0,
            "comments": item.get("comments") or item.get("commentsCount") or 0,
        })

    if not posts:
        raise RuntimeError(
            "Apify ran successfully but returned no usable post text. "
            "Check the actor's output in the Apify console."
        )

    return posts


# ── Groq / LLaMA Prompt Generator ───────────────────────────────────────────

def build_groq_prompt(posts: list[dict]) -> str:
    """Build the user message that includes the actual scraped post content."""
    today = datetime.now().strftime("%A, %B %d %Y")

    posts_block = ""
    for i, p in enumerate(posts, 1):
        date_str = f" ({p['date']})" if p["date"] else ""
        eng_str = f"  [👍 {p['likes']}  💬 {p['comments']}]" if p["likes"] or p["comments"] else ""
        posts_block += (
            f"--- Post {i}{date_str}{eng_str} ---\n"
            f"{p['text']}\n\n"
        )

    return f"""Today is {today}.

You are a LinkedIn content strategist for {AUTHOR_PROFILE['name']}, 
a {AUTHOR_PROFILE['role']} in Nigeria.
Their audience: {AUTHOR_PROFILE['audience']}
Their tone: {AUTHOR_PROFILE['tone']}

Below are the {len(posts)} most recent posts published by Tech4Dev on LinkedIn.
Study them carefully — the topics they're covering, their language, what's getting 
engagement, and any campaigns or themes they're pushing right now.

== TECH4DEV RECENT POSTS ==
{posts_block}
== END OF POSTS ==

Based on THESE SPECIFIC posts and what Tech4Dev is currently talking about, generate 
3 distinct LinkedIn post prompts that Emenike could write THIS WEEK. Each prompt 
should react to, expand on, add a personal angle to, or complement the content 
Tech4Dev is actively publishing.

Do NOT give generic prompts. Every prompt must reference or connect to something 
specific from the posts above.

Return ONLY a valid JSON array with exactly 3 objects. Each object:
{{
  "title": "Short title for this prompt idea",
  "tech4dev_connection": "Which post or theme from above this connects to (be specific)",
  "post_angle": "The specific personal angle Emenike should take",
  "hook": "Suggested opening line for the post",
  "key_points": ["point 1", "point 2", "point 3"],
  "cta": "Closing question or call-to-action",
  "hashtags": ["tag1", "tag2", "tag3", "tag4"],
  "length": "short | medium | long",
  "why_now": "Why posting this in response to Tech4Dev's activity is timely"
}}

Return ONLY the JSON array. No markdown. No preamble."""


GROQ_SYSTEM = (
    "You are an expert LinkedIn content strategist specialising in African tech "
    "and business audiences. You always ground your advice in the actual source "
    "material provided, never in generic advice."
)


def generate_prompts_with_groq(posts: list[dict]) -> list[dict]:
    """Call Groq free API (llama-3.3-70b-versatile) to generate post prompts."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY secret is not set in GitHub.")

    user_msg = build_groq_prompt(posts)

    payload = json.dumps({
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": GROQ_SYSTEM},
            {"role": "user",   "content": user_msg},
        ],
        "temperature": 0.8,
        "max_tokens": 2000,
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST"
    )

    print("🤖 Calling Groq LLaMA 3.3 70B...")
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read())

    raw = data["choices"][0]["message"]["content"].strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    prompts = json.loads(raw)
    print(f"✅ Generated {len(prompts)} post prompts.")
    return prompts


# ── Email Formatter ──────────────────────────────────────────────────────────

def format_email(prompts: list[dict], posts: list[dict]) -> str:
    today = datetime.now().strftime("%A, %B %d, %Y")
    num_posts = len(posts)

    prompt_cards = ""
    for i, p in enumerate(prompts, 1):
        tags = " ".join(f"#{t.lstrip('#')}" for t in p.get("hashtags", []))
        points_html = "".join(
            f"<li style='margin-bottom:6px;color:#444;'>{pt}</li>"
            for pt in p.get("key_points", [])
        )
        length_color = {"short": "#2196F3", "medium": "#FF9800", "long": "#9C27B0"}.get(
            p.get("length", "medium"), "#555"
        )

        prompt_cards += f"""
        <div style="border:1px solid #e0e0e0; border-radius:12px; margin-bottom:28px; overflow:hidden;">
          <!-- Card header -->
          <div style="background:#0A66C2; padding:14px 20px; display:flex; justify-content:space-between; align-items:center;">
            <span style="color:white; font-weight:700; font-size:16px;">Prompt {i} of {len(prompts)}</span>
            <span style="background:rgba(255,255,255,0.2); color:white; padding:3px 10px; border-radius:20px; font-size:12px;">
              {p.get('length','medium').upper()}
            </span>
          </div>
          <!-- Card body -->
          <div style="padding:20px; background:white;">

            <h3 style="margin:0 0 6px; color:#1a1a1a; font-size:17px;">{p.get('title','')}</h3>

            <div style="background:#EEF3FB; border-left:3px solid #0A66C2; padding:10px 14px; border-radius:4px; margin-bottom:16px;">
              <strong style="color:#0A66C2; font-size:12px; text-transform:uppercase; letter-spacing:.5px;">🔗 Connected to Tech4Dev Post</strong>
              <p style="margin:4px 0 0; color:#333; font-size:13px;">{p.get('tech4dev_connection','')}</p>
            </div>

            <strong style="color:#555; font-size:12px; text-transform:uppercase; letter-spacing:.5px;">💡 Your Angle</strong>
            <p style="color:#333; margin:4px 0 16px; line-height:1.6;">{p.get('post_angle','')}</p>

            <strong style="color:#555; font-size:12px; text-transform:uppercase; letter-spacing:.5px;">🪝 Hook</strong>
            <div style="background:#FFF8E7; border:1px solid #FFD700; border-radius:8px; padding:12px 16px; margin:6px 0 16px; font-style:italic; color:#333; line-height:1.6;">
              "{p.get('hook','')}"
            </div>

            <strong style="color:#555; font-size:12px; text-transform:uppercase; letter-spacing:.5px;">📌 Key Points to Cover</strong>
            <ul style="margin:6px 0 16px; padding-left:20px;">{points_html}</ul>

            <strong style="color:#555; font-size:12px; text-transform:uppercase; letter-spacing:.5px;">📣 Call to Action</strong>
            <p style="color:#333; margin:4px 0 16px; line-height:1.6;">{p.get('cta','')}</p>

            <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:12px;">
              {"".join(f'<span style="background:#EEF3FB;color:#0A66C2;padding:4px 10px;border-radius:20px;font-size:12px;">{t}</span>' for t in tags.split())}
            </div>

            <div style="background:#F1F8E9; border-radius:8px; padding:10px 14px;">
              <strong style="color:#388E3C; font-size:12px;">⚡ Why post this now?</strong>
              <p style="color:#333; margin:4px 0 0; font-size:13px;">{p.get('why_now','')}</p>
            </div>
          </div>
        </div>
        """

    # Recent posts preview (collapsed summary)
    recent_preview = ""
    for post in posts[:3]:
        snippet = post["text"][:120].replace("<", "&lt;").replace(">", "&gt;")
        recent_preview += f"""
        <div style="border-bottom:1px solid #eee; padding:10px 0; font-size:12px; color:#666;">
          <span style="color:#0A66C2;">▶</span> {snippet}…
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0; padding:20px; background:#F3F2EE; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">

  <div style="max-width:620px; margin:0 auto;">

    <!-- Header -->
    <div style="background:#0A66C2; border-radius:12px 12px 0 0; padding:28px 24px; text-align:center;">
      <div style="font-size:28px; margin-bottom:8px;">📝</div>
      <h1 style="color:white; margin:0; font-size:22px; font-weight:700;">LinkedIn Post Prompts</h1>
      <p style="color:rgba(255,255,255,0.85); margin:6px 0 0; font-size:14px;">
        Based on <strong>{num_posts} real Tech4Dev posts</strong> scraped today · {today}
      </p>
    </div>

    <!-- Body -->
    <div style="background:#f9f9f9; padding:24px; border-radius:0 0 12px 12px;">

      <div style="background:#E3F2FD; border-radius:8px; padding:14px 18px; margin-bottom:24px; font-size:13px; color:#1565C0;">
        <strong>✅ Live data used:</strong> These prompts are based on what Tech4Dev actually posted 
        on LinkedIn recently — not generic templates. Each prompt connects directly to their current activity.
      </div>

      {prompt_cards}

      <!-- Recent posts preview -->
      <div style="background:white; border:1px solid #e0e0e0; border-radius:12px; padding:18px; margin-top:8px;">
        <strong style="color:#555; font-size:12px; text-transform:uppercase; letter-spacing:.5px;">
          📡 Tech4Dev Posts Used as Source ({num_posts} scraped)
        </strong>
        {recent_preview}
        <p style="font-size:11px; color:#aaa; margin-top:10px; margin-bottom:0;">
          + {max(0, num_posts-3)} more posts were also analysed · 
          <a href="{TECH4DEV_LINKEDIN_URL}" style="color:#0A66C2;">View Tech4Dev on LinkedIn →</a>
        </p>
      </div>

      <p style="color:#bbb; font-size:11px; text-align:center; margin-top:20px;">
        LinkedIn Prompt Bot · Emenike Madukairo · Delivered every Monday & Wednesday
      </p>
    </div>
  </div>
</body>
</html>"""


# ── Email Sender ─────────────────────────────────────────────────────────────

def send_email(html: str):
    sender    = os.environ.get("EMAIL_SENDER")
    password  = os.environ.get("EMAIL_PASSWORD")
    recipient = os.environ.get("EMAIL_RECIPIENT", sender)

    if not sender or not password:
        raise ValueError("EMAIL_SENDER or EMAIL_PASSWORD is not set.")

    print(f"DEBUG sender: {'***' if sender else 'MISSING'}")
    print(f"DEBUG recipient: {'***' if recipient else 'MISSING'}")

    today = datetime.now().strftime("%A, %b %d")
    subject = f"📝 Your LinkedIn Prompts for {today} — Based on Live Tech4Dev Posts"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, password)
        server.sendmail(sender, recipient, msg.as_string())

    print(f"✅ Email sent to {recipient}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"🚀 Tech4Dev LinkedIn Agent starting — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    # 1. Scrape real posts from LinkedIn via Apify
    posts = scrape_tech4dev_posts()
    print()

    # 2. Generate prompts grounded in those posts
    prompts = generate_prompts_with_groq(posts)
    print()

    # 3. Send the email
    print("📧 Sending email...")
    html = format_email(prompts, posts)
    send_email(html)
    print()
    print("🎉 Done!")


if __name__ == "__main__":
    main()
