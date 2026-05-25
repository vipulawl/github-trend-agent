import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _repo_rows(repos: list[dict]) -> str:
    rows = ""
    for r in repos:
        lang = f" <span style='color:#6e7681'>({r['language']})</span>" if r["language"] else ""
        today = f" <span style='color:#2da44e'>+{r['stars_today']}</span>" if r["stars_today"] else ""
        desc = f"<br><span style='color:#6e7681;font-size:13px'>{r['description']}</span>" if r["description"] else ""
        rows += f"""
        <tr>
          <td style='padding:8px 0;border-bottom:1px solid #21262d'>
            <a href='{r["url"]}' style='color:#58a6ff;font-weight:600;text-decoration:none'>{r['full_name']}</a>{lang}{today}{desc}
          </td>
        </tr>"""
    return rows


def _hn_rows(stories: list[dict]) -> str:
    rows = ""
    for s in stories:
        link_url = s["url"] if s["url"] else s["hn_url"]
        rows += f"""
        <tr>
          <td style='padding:8px 0;border-bottom:1px solid #21262d'>
            <a href='{link_url}' style='color:#58a6ff;font-weight:600;text-decoration:none'>{s["title"]}</a><br>
            <span style='color:#6e7681;font-size:12px'>
              {s["score"]} pts &nbsp;·&nbsp; {s["comments"]} comments &nbsp;·&nbsp;
              <a href='{s["hn_url"]}' style='color:#8b949e;text-decoration:none'>HN discussion</a>
            </span>
          </td>
        </tr>"""
    return rows


def _section(title: str, icon: str, rows_html: str, count: int) -> str:
    if not rows_html:
        return ""
    return f"""
    <div style='margin-bottom:28px'>
      <h2 style='color:#e6edf3;font-size:16px;margin:0 0 12px 0;padding-bottom:8px;border-bottom:1px solid #30363d'>
        {icon} {title} <span style='color:#6e7681;font-weight:normal;font-size:13px'>({count})</span>
      </h2>
      <table style='width:100%;border-collapse:collapse'>{rows_html}</table>
    </div>"""


def build_html(new_repos: list, new_stories: list, run_time: str) -> str:
    total = len(new_repos) + len(new_stories)
    body = (
        _section("Trending Repos", "🔥", _repo_rows(new_repos), len(new_repos)) +
        _section("Hacker News", "📰", _hn_rows(new_stories), len(new_stories))
    )
    return f"""
<!DOCTYPE html>
<html>
<body style='background:#0d1117;color:#e6edf3;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;margin:0;padding:0'>
  <div style='max-width:680px;margin:0 auto;padding:24px 16px'>
    <div style='margin-bottom:24px'>
      <h1 style='color:#e6edf3;font-size:20px;margin:0 0 4px 0'>GitHub Trend Alert</h1>
      <p style='color:#6e7681;font-size:13px;margin:0'>{run_time} &nbsp;·&nbsp; {total} items</p>
    </div>
    {body}
    <p style='color:#484f58;font-size:12px;margin-top:24px'>github-trend-agent — daily digest</p>
  </div>
</body>
</html>"""


def send_email(new_repos: list, new_stories: list) -> bool:
    gmail_user = os.environ["GMAIL_USER"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    to_email = os.environ.get("TO_EMAIL", gmail_user)

    run_time = datetime.now().strftime("%b %d, %Y")
    total = len(new_repos) + len(new_stories)
    subject = f"[Daily Digest] {total} items — {run_time}"

    html = build_html(new_repos, new_stories, run_time)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, app_password)
        server.sendmail(gmail_user, to_email, msg.as_string())

    print(f"  [email] sent to {to_email}: {subject}")
    return True
