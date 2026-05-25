#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from github_monitor import get_trending_repos
from hn_monitor import get_hn_github_stories
from email_sender import send_email

STATE_FILE = Path(__file__).parent / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"repos": [], "hn_stories": [], "last_sent_date": ""}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def filter_new(items: list, seen_ids: list, id_key: str) -> tuple[list, list]:
    seen_set = set(seen_ids)
    new_items = [i for i in items if i[id_key] not in seen_set]
    updated_seen = list(seen_set | {i[id_key] for i in items})
    updated_seen = updated_seen[-500:]
    return new_items, updated_seen


def main():
    parser = argparse.ArgumentParser(description="GitHub trend monitoring agent")
    parser.add_argument("--force", action="store_true",
                        help="Send email even if already sent today (for testing)")
    args = parser.parse_args()

    for var in ("GMAIL_USER", "GMAIL_APP_PASSWORD"):
        if not os.getenv(var):
            print(f"ERROR: {var} not set in .env")
            sys.exit(1)

    languages_raw = os.getenv("LANGUAGES", "Python,JavaScript,TypeScript")
    languages = [l.strip() for l in languages_raw.split(",") if l.strip()] if languages_raw else []
    min_score = int(os.getenv("HN_MIN_SCORE") or "50")
    max_age_days = int(os.getenv("MAX_REPO_AGE_DAYS") or "30")

    today = datetime.now().strftime("%Y-%m-%d")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting GitHub trend agent")
    print(f"  Languages: {languages or 'all'} | HN min score: {min_score} | Max repo age: {max_age_days} days")

    state = load_state()

    if state.get("last_sent_date") == today and not args.force:
        print("  Already sent today — skipping. Use --force to override.")
        return

    print("  Fetching GitHub trending repos...")
    all_repos = get_trending_repos(languages, max_age_days=max_age_days)
    print(f"  → {len(all_repos)} repos after age filter")

    print("  Fetching HN stories...")
    all_stories = get_hn_github_stories(min_score)
    print(f"  → {len(all_stories)} HN stories found")

    new_repos, updated_repo_ids = filter_new(all_repos, state["repos"], "full_name")
    new_stories, updated_story_ids = filter_new(all_stories, state.get("hn_stories", []), "id")

    total_new = len(new_repos) + len(new_stories)
    print(f"  New: {len(new_repos)} repos, {len(new_stories)} HN stories")

    if total_new == 0 and not args.force:
        print("  Nothing new — skipping email.")
        return

    if args.force and total_new == 0:
        print("  --force: sending email with all found items")
        new_repos, new_stories = all_repos[:10], all_stories[:10]

    print("  Sending email...")
    send_email(new_repos, new_stories)

    state["repos"] = updated_repo_ids
    state["hn_stories"] = updated_story_ids
    state["last_sent_date"] = today
    save_state(state)
    print("  State saved.")


if __name__ == "__main__":
    main()
