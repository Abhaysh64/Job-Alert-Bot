"""
Job Alert Digest
Scrapes LinkedIn, Indeed, Naukri & Google Jobs daily.
Deduplicates results, filters by keywords, sends a Telegram digest.
"""

import os
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from jobspy import scrape_jobs

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config (edit this section) ───────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]   # set as GitHub secret
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]     # your personal chat ID

SEARCH_QUERIES = [
    "Full Stack Developer",
    "Backend Developer Python",
    "Software Engineer Node.js",
    "AI Engineer LangChain",
]

LOCATION = "India"   # change to "Remote" or a specific city

# Only surface jobs whose title contains at least one of these (case-insensitive).
# Empty list = no filter.
TITLE_KEYWORDS = [
    "full stack", "backend", "software engineer",
    "python developer", "node", "ai engineer",
    "ml engineer", "llm", "langchain",
]

# Skip jobs whose title contains any of these.
TITLE_BLOCKLIST = ["senior principal", "vp ", "director", "head of", "intern"]

# How many hours back to look (24 = jobs posted in last 24 hrs)
HOURS_OLD = 24

# Max results per query per site
RESULTS_PER_QUERY = 15

# File that persists seen job IDs across runs (committed to repo or stored in /tmp)
SEEN_FILE = Path("seen_jobs.json")

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_seen() -> set:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()


def save_seen(seen: set) -> None:
    SEEN_FILE.write_text(json.dumps(list(seen)))


def job_id(row: pd.Series) -> str:
    """Stable hash from company + title + URL."""
    key = f"{row.get('company','')}{row.get('title','')}{row.get('job_url','')}".lower()
    return hashlib.md5(key.encode()).hexdigest()


def passes_filter(title: str) -> bool:
    t = title.lower()
    if TITLE_KEYWORDS and not any(kw in t for kw in TITLE_KEYWORDS):
        return False
    if any(bl in t for bl in TITLE_BLOCKLIST):
        return False
    return True


# ── Scraping ──────────────────────────────────────────────────────────────────

def fetch_jobs() -> pd.DataFrame:
    frames = []
    for query in SEARCH_QUERIES:
        log.info("Searching: %s", query)
        try:
            df = scrape_jobs(
                site_name=["linkedin", "indeed", "naukri", "google"],
                search_term=query,
                location=LOCATION,
                results_wanted=RESULTS_PER_QUERY,
                hours_old=HOURS_OLD,
                country_indeed="India",
            )
            frames.append(df)
            log.info("  → %d results", len(df))
        except Exception as exc:
            log.warning("  Query failed (%s): %s", query, exc)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # keep useful columns only
    cols = ["title", "company", "location", "job_url", "site", "date_posted",
            "is_remote", "job_type", "min_amount", "max_amount", "currency"]
    combined = combined[[c for c in cols if c in combined.columns]]
    return combined.drop_duplicates(subset=["job_url"])


# ── Filtering & dedup ─────────────────────────────────────────────────────────

def filter_new(df: pd.DataFrame, seen: set) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["_id"] = df.apply(job_id, axis=1)
    df = df[~df["_id"].isin(seen)]
    df = df[df["title"].apply(passes_filter)]
    return df


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()


def format_job(row: pd.Series, index: int) -> str:
    title   = row.get("title", "N/A")
    company = row.get("company", "N/A")
    loc     = row.get("location", "N/A") or "N/A"
    remote  = " 🌐 Remote" if row.get("is_remote") else ""
    site    = str(row.get("site", "")).capitalize()
    url     = row.get("job_url", "#")

    salary = ""
    mn, mx, cur = row.get("min_amount"), row.get("max_amount"), row.get("currency", "")
    if pd.notna(mn) and pd.notna(mx):
        salary = f"\n💰 {cur} {int(mn):,} – {int(mx):,}/yr"
    elif pd.notna(mn):
        salary = f"\n💰 {cur} {int(mn):,}+/yr"

    return (
        f"{index}. <b>{title}</b>\n"
        f"🏢 {company}  |  📍 {loc}{remote}\n"
        f"🔗 <a href='{url}'>{site}</a>{salary}"
    )


def build_digest(df: pd.DataFrame) -> list[str]:
    """Return a list of Telegram messages (split if > 4096 chars)."""
    date_str = datetime.now().strftime("%a, %d %b %Y")
    header = (
        f"🔔 <b>Job Digest — {date_str}</b>\n"
        f"Found <b>{len(df)}</b> new matching jobs\n"
        f"{'─' * 30}\n\n"
    )

    messages, current, idx = [], header, 1
    for _, row in df.iterrows():
        block = format_job(row, idx) + "\n\n"
        if len(current) + len(block) > 4000:
            messages.append(current)
            current = block
        else:
            current += block
        idx += 1

    if current.strip():
        messages.append(current)

    if not messages:
        messages = [f"🔔 <b>Job Digest — {date_str}</b>\n\nNo new jobs found today. Check back tomorrow!"]

    return messages


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    log.info("Starting job alert digest...")

    seen = load_seen()
    log.info("Loaded %d previously seen jobs", len(seen))

    raw = fetch_jobs()
    log.info("Total scraped (before filter): %d", len(raw))

    fresh = filter_new(raw, seen)
    log.info("New jobs after dedup + filter: %d", len(fresh))

    # Sort: remote first, then by date
    if not fresh.empty and "date_posted" in fresh.columns:
        fresh = fresh.sort_values(
            by=["is_remote", "date_posted"],
            ascending=[False, False],
            na_position="last",
        )

    messages = build_digest(fresh)
    for msg in messages:
        send_telegram(msg)
        log.info("Telegram message sent (%d chars)", len(msg))

    # Persist seen IDs
    if not fresh.empty:
        new_ids = set(fresh["_id"].tolist())
        save_seen(seen | new_ids)
        log.info("Saved %d new job IDs to seen list", len(new_ids))

    log.info("Done.")


if __name__ == "__main__":
    main()
