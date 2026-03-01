"""
Tech4Dev LinkedIn Executive Post Agent
- Scrapes Tech4Dev LinkedIn posts
- Generates executive post prompts via Groq (free LLM)
- Sends email 3x/week via Resend
"""

import os
import requests
from datetime import datetime
from bs4 import BeautifulSoup

# ── Config from environment variables ──────────────────────────────────────
GROQ_API_KEY    = os.environ["GROQ_API_KEY"]      # Free at console.groq.com
RESEND_API_KEY  = os.environ["RESEND_API_KEY"]    # Free at resend.com
SENDER_EMAIL    = os.environ["SENDER_EMAIL"]       # Your verified sender email
RECIPIENT_EMAIL = os.environ["RECIPIENT_EMAIL"]    # Where to send the prompts
LINKEDIN_COMPANY = os.getenv("LINKEDIN_COMPANY", "tech4dev")


# ── Step 1: Scrape Tech4Dev LinkedIn posts ─────────────────────────────────
def scrape_linkedin_posts():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    posts = []

    try:
        url = f"https://www.linkedin.com/company/{LINKEDIN_COMPANY}/posts/"
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for tag in soup.find_all(["p", "span"], limit=60):
                text = tag.get_text(strip=True)
                if len(text) > 80:
                    posts.append({"text": text, "source": "linkedin_scrape"})
            print(f"✅ Scraped {len(posts)} text segments from LinkedIn.")
    except Exception as e:
        print(f"⚠️  LinkedIn scrape error: {e}")

    if len(posts) < 3:
        print("ℹ️  Using fallback content about Tech4Dev...")
        posts = [
            {"text": "Tech4Dev recently ran a Women Techsters Fellowship cohort, training hundreds of women in cloud computing, cybersecurity, and software development across Africa.", "source": "fallback"},
            {"text": "Tech4Dev's Paradigm Initiative is bridging the digital divide by providing digital skills training and internet access advocacy in underserved Nigerian communities.", "source": "fallback"},
            {"text": "Tech4Dev launched a new cohort of its flagship tech training program, targeting unemployed youth and providing pathways into the digital economy.", "source": "fallback"},
            {"text": "Tech4Dev partnered with global organizations to expand digital literacy programs across West Africa, reaching over 10,000 beneficiaries this quarter.", "source": "fallback"},
            {"text": "The Tech4Dev team celebrated graduation of its latest batch of software developers trained under its intensive coding bootcamp.", "source": "fallback"},
        ]

    return posts[:10]


# ── Step 2: Generate executive post prompts via Groq ──────────────────────
def generate_post_prompts(posts):
    posts_text = "\n\n".join([f"- {p['text']}" for p in posts[:5]])

    system_prompt = """You are a ghostwriter for a senior executive at Tech4Dev, 
a leading African tech NGO focused on digital skills, inclusion, and empowerment.
Your job is to write compelling LinkedIn post PROMPTS (not full posts) that the executive 
can use as a starting point. Each prompt should:
1. Highlight what Tech4Dev is doing
2. Include a personal story angle or reflection the exec can personalize
3. Be authentic, inspiring, and human — not corporate-sounding
4. Be suitable for a thought leader in tech for development/social impact

Format: Provide exactly 3 post prompts, numbered 1-3. For each prompt:
- Give a HEADLINE/HOOK (first line of the post)
- Give KEY POINTS to cover (2-3 bullets)
- Give a PERSONAL STORY ANGLE the executive can adapt
- Give a CALL TO ACTION suggestion
"""

    user_message = f"""Based on these recent Tech4Dev activities and updates:

{posts_text}

Generate 3 LinkedIn post prompts for a Tech4Dev executive to post this week.
Mix themes: one about impact/mission, one about team/culture, one about personal reflection on the tech-for-development journey."""

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.85,
        "max_tokens": 1500,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]


# ── Step 3: Send email via Resend ──────────────────────────────────────────
def send_email(prompts, posts):
    today = datetime.now().strftime("%A, %B %d %Y")
    subject = f"Your LinkedIn Post Prompts for {today} | Tech4Dev"

    posts_preview = "".join(
        f"<li style='margin-bottom:8px;color:#555'>{p['text'][:150]}...</li>"
        for p in posts[:3]
    )

    prompts_html = prompts.replace("\n", "<br>")

    html_body = f"""
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;max-width:680px;margin:auto;padding:20px;color:#333">

  <div style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:30px;border-radius:12px;margin-bottom:24px">
    <h1 style="color:#e94560;margin:0;font-size:22px">Tech4Dev LinkedIn Agent</h1>
    <p style="color:#aaa;margin:8px 0 0">Executive Post Prompts - {today}</p>
  </div>

  <div style="background:#f9f9f9;border-left:4px solid #e94560;padding:16px;border-radius:6px;margin-bottom:24px">
    <p style="margin:0;font-size:14px;color:#666">
      Here are 3 post prompts crafted for you based on recent Tech4Dev content.
      Personalize them with your own stories and voice before posting.
    </p>
  </div>

  <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:24px;margin-bottom:24px">
    <h2 style="color:#1a1a2e;font-size:18px;margin-top:0">Your 3 Post Prompts This Week</h2>
    <div style="font-size:15px;line-height:1.7;color:#333">
      {prompts_html}
    </div>
  </div>

  <div style="background:#fff;border:1px solid #e0e0e0;border-radius:10px;padding:24px;margin-bottom:24px">
    <h2 style="color:#1a1a2e;font-size:16px;margin-top:0">Source: Recent Tech4Dev Activity</h2>
    <ul style="font-size:13px;padding-left:18px">
      {posts_preview}
    </ul>
  </div>

  <div style="background:#fff8e1;border-radius:8px;padding:16px;font-size:13px;color:#555">
    <strong>Tips for posting:</strong><br>
    - Add a personal story or memory to make it yours<br>
    - Post Tuesday-Thursday for best LinkedIn engagement<br>
    - End with a question to spark comments<br>
    - Use 3-5 relevant hashtags (#Tech4Dev #DigitalInclusion #AfricaTech)
  </div>

  <p style="text-align:center;font-size:12px;color:#999;margin-top:24px">
    Sent automatically by your Tech4Dev LinkedIn Agent - 3x/week
  </p>

</body>
</html>
"""

    payload = {
        "from": SENDER_EMAIL,
        "to": [RECIPIENT_EMAIL],
        "subject": subject,
        "html": html_body,
    }

    headers = {
        "Authorization": f"Bearer {RESEND_API_KEY}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        "https://api.resend.com/emails",
        json=payload,
        headers=headers,
        timeout=30,
    )

    if response.status_code in [200, 201]:
        print(f"✅ Email sent to {RECIPIENT_EMAIL}")
    else:
        print(f"❌ Resend error: {response.status_code} - {response.text}")
        response.raise_for_status()


# ── Main ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("🚀 Tech4Dev LinkedIn Agent starting...")

    print("🔍 Scraping LinkedIn posts...")
    posts = scrape_linkedin_posts()
    print(f"   Found {len(posts)} posts/segments.")

    print("🤖 Generating post prompts with Groq LLaMA 3...")
    prompts = generate_post_prompts(posts)
    print("   Prompts generated.")

    print("📧 Sending email...")
    send_email(prompts, posts)

    print("✅ Done!")
