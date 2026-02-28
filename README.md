# 🤖 Tech4Dev LinkedIn Executive Post Agent

An automated agent that scrapes Tech4Dev's LinkedIn, generates executive-style post prompts using a free AI, and emails them to you **3x per week** — fully automated via GitHub Actions.

---

## 🏗️ Architecture

```
GitHub Actions (Mon/Wed/Fri 7AM WAT)
        │
        ▼
  scripts/agent.py
        │
        ├── 1. Scrape Tech4Dev LinkedIn posts
        │        (linkedin.com/company/tech4dev)
        │
        ├── 2. Generate prompts via Groq API (FREE)
        │        Model: LLaMA 3 8B
        │
        └── 3. Send HTML email via Gmail SMTP
```

---

## 🚀 Setup Guide (5 Minutes)

### Step 1: Get Free Groq API Key
1. Go to [console.groq.com](https://console.groq.com)
2. Sign up (free — no credit card needed)
3. Go to **API Keys** → **Create API Key**
4. Copy the key (starts with `gsk_...`)

### Step 2: Set Up Gmail App Password
> ⚠️ You need a Gmail App Password, NOT your regular Gmail password.

1. Go to your Google Account → **Security**
2. Enable **2-Step Verification** if not already on
3. Go to **App Passwords** (search for it in your Google Account)
4. Create a new App Password for "Mail" → Copy the 16-character password

### Step 3: Fork & Configure the Repo
1. **Fork** this repository to your GitHub account
2. Go to your forked repo → **Settings** → **Secrets and variables** → **Actions**
3. Add these 4 secrets (click "New repository secret" for each):

| Secret Name | Value |
|-------------|-------|
| `GROQ_API_KEY` | Your Groq API key (`gsk_...`) |
| `SENDER_EMAIL` | Your Gmail address (e.g. `you@gmail.com`) |
| `SENDER_PASSWORD` | Your Gmail App Password (16 chars) |
| `RECIPIENT_EMAIL` | Where to receive prompts (can be same email) |

### Step 4: Enable GitHub Actions
1. Go to your repo → **Actions** tab
2. Click **"I understand my workflows, go ahead and enable them"**
3. That's it! The agent will run automatically Mon/Wed/Fri.

### Step 5: Test It Manually
1. Go to **Actions** → **Tech4Dev LinkedIn Post Agent**
2. Click **"Run workflow"** → **"Run workflow"**
3. Check your email in ~2 minutes! 📬

---

## 📅 Schedule

| Day | Time (Lagos WAT) |
|-----|-----------------|
| Monday | 7:00 AM |
| Wednesday | 7:00 AM |
| Friday | 7:00 AM |

---

## 📧 What You'll Receive

Each email contains:
- **3 LinkedIn post prompts** tailored for a Tech4Dev executive
- Each prompt includes:
  - 🎣 Hook/headline to start with
  - 📌 Key points to cover
  - 💬 Personal story angle to customize
  - 📢 Call-to-action suggestion
- Source: recent Tech4Dev activities that inspired the prompts
- Posting tips for better engagement

---

## 🛠️ Customization

**Change the schedule** — Edit `.github/workflows/agent.yml`:
```yaml
- cron: "0 6 * * 1"  # Monday at 6AM UTC (7AM WAT)
```
Use [crontab.guru](https://crontab.guru) to customize.

**Change the company** — Edit the `LINKEDIN_COMPANY` env var in the workflow:
```yaml
LINKEDIN_COMPANY: tech4dev
```

**Adjust the AI tone** — Edit the `system_prompt` in `scripts/agent.py` to match your executive's voice.

---

## 🔧 Tech Stack

| Component | Tool | Cost |
|-----------|------|------|
| LLM / AI | Groq + LLaMA 3 8B | **Free** |
| Email | Gmail SMTP | **Free** |
| Automation | GitHub Actions | **Free** (2,000 min/month) |
| Scraping | Python + BeautifulSoup | **Free** |

**Total cost: $0/month** 🎉

---

## ❓ Troubleshooting

**Email not arriving?**
- Check your spam folder
- Verify the Gmail App Password is correct (not your regular password)
- Make sure 2FA is enabled on your Google account

**Groq errors?**
- Verify your API key in GitHub Secrets
- Check [status.groq.com](https://status.groq.com)

**LinkedIn scraping limited?**
- LinkedIn blocks automated scraping aggressively
- The agent has a fallback to use known Tech4Dev activities
- This is expected behavior — the prompts will still be generated and sent

---

## 📁 Project Structure

```
├── .github/
│   └── workflows/
│       └── agent.yml        # GitHub Actions schedule & config
├── scripts/
│   └── agent.py             # Main agent logic
├── requirements.txt         # Python dependencies
└── README.md                # This file
```
