import time
import requests

HN_API = "https://hn.algolia.com/api/v1/search"


def get_hn_github_stories(min_score: int, lookback_hours: int = 24) -> list[dict]:
    """Fetch recent HN stories that mention GitHub and meet the score threshold."""
    since_ts = int(time.time()) - (lookback_hours * 3600)
    results = []

    try:
        resp = requests.get(
            HN_API,
            params={
                "query": "github",
                "tags": "story",
                "hitsPerPage": 50,
                "numericFilters": f"created_at_i>{since_ts},points>={min_score}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"  [hn] fetch failed: {e}")
        return []

    for hit in data.get("hits", []):
        url = hit.get("url", "")
        title = hit.get("title", "")
        if not title:
            continue
        # only include stories that link to or discuss a github repo/project
        if "github.com" not in url and "github" not in title.lower():
            continue
        results.append({
            "id": hit["objectID"],
            "title": title,
            "url": url,
            "hn_url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
            "score": hit.get("points", 0),
            "comments": hit.get("num_comments", 0),
            "author": hit.get("author", ""),
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results
