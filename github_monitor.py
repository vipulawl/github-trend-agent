import os
import re
import requests
from bs4 import BeautifulSoup

GITHUB_API = "https://api.github.com"
TRENDING_URL = "https://github.com/trending"


def _headers():
    token = os.getenv("GITHUB_TOKEN", "")
    h = {"Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _parse_stars_today(text: str) -> int:
    m = re.search(r"([\d,]+)", text)
    return int(m.group(1).replace(",", "")) if m else 0


def _fetch_created_at(repos: list[dict]) -> list[dict]:
    for repo in repos:
        try:
            resp = requests.get(
                f"{GITHUB_API}/repos/{repo['full_name']}",
                headers=_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                repo["created_at"] = resp.json().get("created_at", "")
            elif resp.status_code == 403:
                print("  [github] rate limited — stopping created_at fetch")
                break
        except requests.RequestException:
            pass
    return repos


def get_trending_repos(languages: list[str]) -> list[dict]:
    results = []
    langs_to_check = languages if languages else [None]

    for lang in langs_to_check:
        params = {"since": "daily"}
        if lang:
            params["l"] = lang
        try:
            resp = requests.get(TRENDING_URL, params=params, timeout=15,
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
            stars_today_text = stars_today_el.get_text(strip=True) if stars_today_el else ""

            results.append({
                "full_name": full_name,
                "url": f"https://github.com/{full_name}",
                "description": description,
                "language": repo_lang,
                "stars": stars,
                "stars_today": stars_today_text,
                "stars_today_int": _parse_stars_today(stars_today_text),
                "created_at": "",
            })

    seen = set()
    deduped = []
    for r in results:
        if r["full_name"] not in seen:
            seen.add(r["full_name"])
            deduped.append(r)

    if deduped:
        deduped = _fetch_created_at(deduped)

    # Sort: newest repos first, break ties by stars gained today
    deduped.sort(key=lambda r: (r.get("created_at", ""), r["stars_today_int"]), reverse=True)

    return deduped[:10]
