#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from github_monitor import get_trending_repos, get_hot_issues
from hn_monitor import get_hn_github_stories
from email_sender import send_email

STATE_FILE = Path(__file__).parent / "state.json"


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"repos": [], "issues": [], "hn_stories": []}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def filter_new(items: list, seen_ids: list, id_key: str) -> tuple[list, list]:
    seen_set = set(seen_ids)
    new_items = [i for i in items if i[id_key] not in seen_set]
    updated_seen = list(seen_set | {i[id_key] for i in items})
    # keep state bounded to last 500 entries
    updated_seen = updated_seen[-500:]
    return new_items, updated_seen


def main():
    parser = argparse.ArgumentParser(description="GitHub trend monitoring agent")
    parser.add_argument("--force", action="store_true",
                        help="Send email even if nothing is new (for testing)")
    args = parser.parse_args()

    # Validate required env vars
    for var in ("GMAIL_USER", "GMAIL_APP_PASSWORD"):
        if not os.getenv(var):
            print(f"ERROR: {var} not set in .env")
            sys.exit(1)

    languages_raw = os.getenv("LANGUAGES", "Python,JavaScript,TypeScript")
    languages = [l.strip() for l in languages_raw.split(",") if l.strip()] if languages_raw else []
    min_score = int(os.getenv("HN_MIN_SCORE") or "50")
    min_comments = int(os.getenv("ISSUE_MIN_COMMENTS") or "5")

    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Starting GitHub trend agent")
    print(f"  Languages: {languages or 'all'} | HN min score: {min_score} | Issue min comments: {min_comments}")

    state = load_state()

    print("  Fetching GitHub trending repos...")
    all_repos = get_trending_repos(languages)
    print(f"  → {len(all_repos)} repos found")

    print("  Fetching hot issues from trending repos...")
    all_issues = get_hot_issues(all_repos, min_comments)
    print(f"  → {len(all_issues)} hot issues found")

    print("  Fetching HN GitHub stories...")
    all_stories = get_hn_github_stories(min_score)
    print(f"  → {len(all_stories)} HN stories found")

    new_repos, updated_repo_ids = filter_new(all_repos, state["repos"], "full_name")
    new_issues, updated_issue_ids = filter_new(all_issues, state["issues"], "url")
    new_stories, updated_story_ids = filter_new(all_stories, state["hn_stories"], "id")

    total_new = len(new_repos) + len(new_issues) + len(new_stories)
    print(f"  New: {len(new_repos)} repos, {len(new_issues)} issues, {len(new_stories)} HN stories")

    if total_new == 0 and not args.force:
        print("  Nothing new — skipping email.")
        return

    if args.force and total_new == 0:
        print("  --force: sending email with all found items")
        new_repos, new_issues, new_stories = all_repos[:10], all_issues[:10], all_stories[:10]

    print("  Sending email...")
    send_email(new_repos, new_issues, new_stories)

    state["repos"] = updated_repo_ids
    state["issues"] = updated_issue_ids
    state["hn_stories"] = updated_story_ids
    save_state(state)
    print("  State saved.")


if __name__ == "__main__":
    main()
