import os
import re
import requests
from datetime import datetime, timezone

TOKEN = os.environ["STATS_PAT"]
USERNAME = os.environ["GH_USERNAME"]

HEADERS = {"Authorization": f"bearer {TOKEN}"}
GRAPHQL_URL = "https://api.github.com/graphql"
REST_URL = "https://api.github.com"

# ---- 1. Basic REST stats: followers, account creation date ----
# /users/{username} only returns PUBLIC info about someone. Followers/created_at
# are public anyway, so this part is fine as-is.
r = requests.get(f"{REST_URL}/users/{USERNAME}", headers=HEADERS).json()
followers = r["followers"]
created_at = datetime.strptime(r["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

# ---- 2. Uptime: time since account creation (swap for your own reference date if you prefer) ----
now = datetime.now(timezone.utc)
delta = now - created_at
years, days = divmod(delta.days, 365)
uptime = f"{years} years, {days} days"

# ---- 3. Repo count + total stars, INCLUDING PRIVATE REPOS ----
# /user/repos (no username in the path) is the "authenticated user" endpoint —
# since the token belongs to you, this includes your private repos too.
# affiliation=owner means only repos you own (not ones you're just a
# collaborator/org-member on).
repo_count = 0
stars = 0
page = 1
while True:
    resp = requests.get(
        f"{REST_URL}/user/repos",
        headers=HEADERS,
        params={
            "per_page": 100,
            "page": page,
            "affiliation": "owner",
            "visibility": "all",  # public AND private
        },
    ).json()
    if not resp:
        break
    for repo in resp:
        repo_count += 1
        if not repo["fork"]:
            stars += repo["stargazers_count"]
    page += 1

# ---- 4. Total commit contributions, summed year by year via GraphQL ----
# Using "viewer" instead of "user(login: ...)" queries as YOU, the token
# owner — this is what unlocks private-repo commit counts. Querying by
# login only ever returns public contribution numbers, even for your own
# account.
total_commits = 0
year_start = created_at
while year_start < now:
    year_end = min(year_start.replace(year=year_start.year + 1), now)
    query = """
    query($from: DateTime!, $to: DateTime!) {
      viewer {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
        }
      }
    }
    """
    variables = {
        "from": year_start.isoformat(),
        "to": year_end.isoformat(),
    }
    resp = requests.post(
        GRAPHQL_URL, json={"query": query, "variables": variables}, headers=HEADERS
    ).json()
    total_commits += resp["data"]["viewer"]["contributionsCollection"]["totalCommitContributions"]
    year_start = year_end

# ---- 5. Write values into README.md, replacing the placeholder tokens ----
# NOTE: read from README_template.md (which keeps the {{...}} placeholders
# permanently) and write the filled-in result to README.md. This makes the
# script safe to re-run every day.
with open("README_template.md", "r", encoding="utf-8") as f:
    content = f.read()

replacements = {
    "{{UPTIME}}": uptime,
    "{{REPOS}}": str(repo_count),
    "{{COMMITS}}": str(total_commits),
    "{{STARS}}": str(stars),
    "{{FOLLOWERS}}": str(followers),
}

for placeholder, value in replacements.items():
    content = re.sub(re.escape(placeholder), value, content)

with open("README.md", "w", encoding="utf-8") as f:
    f.write(content)

print("Updated README.md:", replacements)
