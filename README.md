# Job Alert Digest Bot 🔔

Scrapes **LinkedIn, Indeed, Naukri & Google Jobs** daily and sends a
formatted Telegram digest every morning at 8 AM IST.

Built with [`python-jobspy`](https://github.com/speedyapply/JobSpy) + GitHub Actions.

---

## What it does

- Searches multiple job boards concurrently for your target roles
- Deduplicates across boards and across days (won't re-send jobs you've seen)
- Filters by title keywords, blocks irrelevant seniority levels
- Sends a clean Telegram message with title, company, location, and direct link
- Runs automatically every morning via GitHub Actions cron — zero maintenance

---

## Setup (5 steps)

### Step 1 — Create a Telegram bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **bot token** (looks like `7123456789:AAFxyz...`)

### Step 2 — Get your Telegram chat ID

1. Start a conversation with your new bot (send it any message)
2. Open this URL in your browser (replace `YOUR_TOKEN`):
   ```
   https://api.telegram.org/botYOUR_TOKEN/getUpdates
   ```
3. Find `"chat": {"id": 123456789}` — that number is your **chat ID**

### Step 3 — Create the GitHub repo

```bash
git init job-alert-bot
cd job-alert-bot
# copy all files here
git add .
git commit -m "init: job alert bot"
git remote add origin https://github.com/YOUR_USERNAME/job-alert-bot.git
git push -u origin main
```

### Step 4 — Add secrets to GitHub

1. Go to your repo → **Settings** → **Secrets and variables** → **Actions**
2. Add two secrets:
   - `TELEGRAM_BOT_TOKEN` → your bot token from Step 1
   - `TELEGRAM_CHAT_ID`   → your chat ID from Step 2

### Step 5 — Enable Actions & test

1. Go to **Actions** tab in your repo
2. Click **"Daily Job Alert Digest"** → **"Run workflow"** to test immediately
3. Check your Telegram — the digest should arrive within ~2 minutes

---

## Customisation

Open `job_alert.py` and edit the **Config** section at the top:

| Variable | What it controls |
|---|---|
| `SEARCH_QUERIES` | Job titles / keywords to search |
| `LOCATION` | City, country, or "Remote" |
| `TITLE_KEYWORDS` | Must-match words in job title |
| `TITLE_BLOCKLIST` | Words that disqualify a job |
| `HOURS_OLD` | How far back to look (24 = last 24 hrs) |
| `RESULTS_PER_QUERY` | Max results per search term per site |

### Change the send time

Edit the cron in `.github/workflows/job_alert.yml`:

```yaml
- cron: "30 2 * * *"   # 2:30 AM UTC = 8:00 AM IST
```

Use [crontab.guru](https://crontab.guru) to build a different schedule.

---

## How deduplication works

`seen_jobs.json` is a list of MD5 hashes (company + title + URL).
After each run the GitHub Action commits the updated file back to the repo,
so the bot remembers what it sent across days.

---

## Project structure

```
job-alert-bot/
├── job_alert.py              # main script
├── requirements.txt
├── seen_jobs.json            # auto-managed, do not delete
└── .github/
    └── workflows/
        └── job_alert.yml     # cron schedule + runner
```
