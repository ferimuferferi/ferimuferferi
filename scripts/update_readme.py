import os
import re
import requests
from datetime import datetime, timezone

TOKEN = os.environ["STATS_PAT"]
USERNAME = os.environ["GH_USERNAME"]

HEADERS = {"Authorization": f"bearer {TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"

# ---- 1. Basic REST stats: followers, public repos, account creation date ----
r = requests.get(f"{REST_URL}/users/{USERNAME}", headers=HEADERS).json()
followers = r["followers"]
public_repos = r["public_repos"]
created_at = datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

# ---- 2. Uptime: time since account creation (swap for your own reference date if you prefer) ----
now = datetime.now(timezone.utc)
delta = now - created_at
years, days = divmod(delta.days, 365)
uptime = f"{years} years, {days} days"

# ---- 3. Total stars across owned, non-fork repos (paginated) ----
stars = 0
page = 1
while True:
    resp = requests.get(
        f"{REST_URL}/users/{USERNAME}/repos",
        headers=HEADERS,
        params={"per_page": 100, "page": page, "type": "owner"},
    ).json()
    if not resp:
        break
    for repo in resp:
        if not repo["fork"]:
            stars += repo["stargazers_count"]
    page += 1

# ---- 4. Total commit contributions, summed year by year via GraphQL ----
total_commits = 0
year_start = created_at
while year_start < now:
    year_end = min(year_start.replace(year=year_start.year + 1), now)
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
        }
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from": year_start.isoformat(),
        "to": year_end.isoformat(),
    }
    resp = requests.post(
        GRAPHQL_URL, json={"query": query, "variables": variables}, headers=HEADERS
    ).json()
    total_commits += resp["data"]["user"]["contributionsCollection"]["totalCommitContributions"]
    year_start = year_end

# ---- 5. Write values into README.md, replacing the placeholder tokens ----
# NOTE: read from README_template.md (which keeps the {{...}} placeholders
# permanently) and write the filled-in result to README.md. This makes the
# script safe to re-run every day.
with open("README_template.md", "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    "{{UPTIME}}": uptime,
    "{{REPOS}}": str(public_repos),
    "{{COMMITS}}": str(total_commits),
    "{{STARS}}": str(stars),
    "{{FOLLOWERS}}": str(followers),
}

for placeholder, value in replacements.items():
    content = re.sub(re.escape(placeholder), value, content)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(content)

print("Updated README.md:", replacements)
