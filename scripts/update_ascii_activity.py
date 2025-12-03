import os
import re
import sys
import datetime as dt
from textwrap import dedent

import requests


README_PATH = "README.md"


def fetch_contributions(token: str, username: str):
    """Get daily contributions for roughly last 1 year."""
    now = dt.datetime.utcnow()
    one_year_ago = now - dt.timedelta(days=370)

    query = dedent(
        """
        query($login: String!, $from: DateTime!, $to: DateTime!) {
          user(login: $login) {
            contributionsCollection(from: $from, to: $to) {
              contributionCalendar {
                weeks {
                  contributionDays {
                    date
                    contributionCount
                  }
                }
              }
            }
          }
        }
        """
    )

    variables = {
        "login": username,
        "from": one_year_ago.isoformat() + "Z",
        "to": now.isoformat() + "Z",
    }

    resp = requests.post(
        "https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

    daily = {}  # date_str -> count
    for week in weeks:
        for day in week["contributionDays"]:
            date_str = day["date"]  # YYYY-MM-DD
            count = day["contributionCount"]
            daily[date_str] = daily.get(date_str, 0) + count

    return daily


def build_weekly_chart(daily):
    """ASCII chart for last 7 days (Sun..Sat)."""
    today = dt.date.today()
    last_7_dates = [today - dt.timedelta(days=i) for i in range(6, -1, -1)]

    # GitHub week starts Sunday usually, ولی ما فقط ۷ روز آخر رو می‌گیریم
    lines = ["# Weekly GitHub Activity (contributions)", ""]
    values = []
    labels = []
    for d in last_7_dates:
        date_str = d.isoformat()
        count = daily.get(date_str, 0)
        values.append(count)
        labels.append(d.strftime("%a"))  # Sun, Mon, ...

    max_val = max(values) if values else 1
    if max_val == 0:
        max_val = 1

    for label, v in zip(labels, values):
        bar_len = int((v / max_val) * 30)  # 30 chars width
        bar = "█" * bar_len + "░" * (30 - bar_len)
        lines.append(f"{label:>3} {v:4d} | {bar}")

    return "\n".join(lines)


def build_monthly_chart(daily):
    """ASCII chart for last 12 months (by total contributions per month)."""
    today = dt.date.today().replace(day=1)
    months = []
    for i in range(11, -1, -1):
        m = today - dt.timedelta(days=30 * i)
        months.append(m)

    # aggregate per YYYY-MM
    month_totals = {}
    for date_str, count in daily.items():
        y, m, _ = date_str.split("-")
        key = f"{y}-{m}"
        month_totals[key] = month_totals.get(key, 0) + count

    lines = ["# Monthly GitHub Activity (last 12 months)", ""]
    values = []
    labels = []
    for m in months:
        key = m.strftime("%Y-%m")
        label = m.strftime("%b %Y")  # Jul 2025
        v = month_totals.get(key, 0)
        values.append(v)
        labels.append(label)

    max_val = max(values) if values else 1
    if max_val == 0:
        max_val = 1

    for label, v in zip(labels, values):
        bar_len = int((v / max_val) * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        lines.append(f"{label} | {bar}  {v:4d}")

    return "\n".join(lines)


def replace_section(content: str, marker: str, new_block: str) -> str:
    pattern = re.compile(
        rf"(<!--START_SECTION:{marker}-->)(.*?)(<!--END_SECTION:{marker}-->)",
        re.DOTALL,
    )
    replacement = rf"\1\n{new_block}\n\3"
    if not pattern.search(content):
        print(f"[WARN] marker {marker} not found")
        return content
    return pattern.sub(replacement, content)


def main():
    username = os.environ.get("GITHUB_USERNAME")
    token = os.environ.get("GH_TOKEN")

    if not username or not token:
        print("GITHUB_USERNAME or GH_TOKEN env not set", file=sys.stderr)
        sys.exit(1)

    if not os.path.exists(README_PATH):
        print("README.md not found", file=sys.stderr)
        sys.exit(1)

    with open(README_PATH, "r", encoding="utf-8") as f:
        readme = f.read()

    daily = fetch_contributions(token, username)

    weekly_chart = build_weekly_chart(daily)
    monthly_chart = build_monthly_chart(daily)

    readme = replace_section(readme, "ascii-week", weekly_chart)
    readme = replace_section(readme, "ascii-month", monthly_chart)

    with open(README_PATH, "w", encoding="utf-8") as f:
        f.write(readme)


if __name__ == "__main__":
    main()
