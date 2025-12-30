import os, json, hashlib
import requests
import feedparser

RSS_URL = os.environ["RSS_URL"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]  # e.g. @mychannel
STATE_FILE = "posted.json"

def load_posted():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_posted(posted_ids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(list(posted_ids)), f)

def stable_id(entry):
    base = entry.get("id") or entry.get("guid") or entry.get("link", "")
    return hashlib.sha256(base.encode("utf-8")).hexdigest()

def openai_summarize(title, link, html_snippet):
    prompt = f"""
Summarize this Google blog post for a Telegram channel.

Title: {title}
Link: {link}

Content (may be partial/HTML):
{html_snippet}

Output rules:
- 4–6 bullet points max
- then one line: "Why it matters: ..."
- no invented facts
- keep under 900 characters
"""

    r = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4.1-mini",
            "input": prompt,
        },
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return data["output"][0]["content"][0]["text"].strip()

def telegram_send(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    r.raise_for_status()

def main():
    posted = load_posted()
    feed = feedparser.parse(RSS_URL)

    # post newest first, but limit so you don't spam if you miss a day
    for entry in feed.entries[:5]:
        eid = stable_id(entry)
        if eid in posted:
            continue

        title = entry.get("title", "Untitled")
        link = entry.get("link", "")
        snippet = entry.get("summary", "")

        summary = openai_summarize(title, link, snippet)
        message = f"{title}\n\n{summary}\n\nSource: {link}"

        telegram_send(message)
        posted.add(eid)

    save_posted(posted)

if __name__ == "__main__":
    main()
