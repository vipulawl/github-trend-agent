import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

GITHUB_API = "https://api.github.com"
TRENDING_URL = "https://github.com/trending"


def _headers():
    token = os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _enrich_with_age(repos: list[dict], max_age_days: int) -> list[dict]:
    """Fetch creation dates via API and drop repos older than max_age_days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    filtered = []
    for repo in repos:
        full_name = repo["full_name"]
        try:
            resp = requests.get(
                f"{GITHUB_API}/repos/{full_name}",
                headers=_headers(),
                timeout=10,
            )
            if resp.status_code == 403:
                print("  [github] rate limited — skipping age filter for remaining repos")
                filtered.append(repo)
                continue
            if resp.status_code != 200:
                filtered.append(repo)
                continue
            data = resp.json()
            created_at = data.get("created_at", "")
            if created_at:
                created_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if created_dt < cutoff:
                    continue
            filtered.append(repo)
        except requests.RequestException:
            filtered.append(repo)
    return filtered


def get_trending_repos(languages: list[str], max_age_days: int = 0) -> list[dict]:
    """Scrape GitHub trending page. Returns list of repo dicts."""
    results = []
    langs_to_check = languages if languages else [None]

    for lang in langs_to_check:
        url = TRENDING_URL
        params = {"since": "daily"}
        if lang:
            params["l"] = lang
        try:
            resp = requests.get(url, params=params, timeout=15,
                                headers={"User-Agent": "github-trend-agent/1.0"})
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [github] trending fetch failed for lang={lang}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")
        for article in soup.select("article.Box-row"):
            name_el = article.select_one("h2 a")
            if not name_el:
                continue
            full_name = name_el.get("href", "").strip("/")
            desc_el = article.select_one("p")
            description = desc_el.get_text(strip=True) if desc_el else ""
            lang_el = article.select_one("[itemprop='programmingLanguage']")
            repo_lang = lang_el.get_text(strip=True) if lang_el else ""
            stars_el = article.select_one("a[href$='/stargazers']")
            stars = stars_el.get_text(strip=True).replace(",", "") if stars_el else "0"
            stars_today_el = article.select_one("span.d-inline-block.float-sm-right")
            stars_today = stars_today_el.get_text(strip=True) if stars_today_el else ""

            results.append({
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": description,
                "language": repo_lang,
                "stars": stars,
                "stars_today": stars_today,
            })

    seen = set()
    deduped = []
    for r in results:
        if r["full_name"] not in seen:
            seen.add(r["full_name"])
            deduped.append(r)

    if max_age_days > 0:
        before = len(deduped)
        deduped = _enrich_with_age(deduped, max_age_days)
        print(f"  → {before - len(deduped)} repos filtered out (older than {max_age_days} days)")

    return deduped
