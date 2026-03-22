import base64
import datetime
import logging
import os
import sqlite3
import sys
import time

import frontmatter
import requests

IS_DEV = os.getenv("DEV", "False").lower() == "true"

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

if not GITHUB_USERNAME:
    raise ValueError("GITHUB_USERNAME environment variable is required")

GITHUB_API_URL = "https://api.github.com"

DB_PATH = "/app/app/data/journals.db" if not IS_DEV else "./journals.db"

logging.basicConfig(
    level=logging.DEBUG if IS_DEV else logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

logger.info("Starting journal collector...")


def fetch_journals():
    # Get user's repositories
    url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/repos?type=owner&sort=pushed&direction=desc&per_page=100"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else None,
        "X-GitHub-Api-Version": "2026-03-10",
    }

    repos = []
    first_loop = True
    next_url = None
    while True:
        if first_loop:
            url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/repos?type=owner&sort=pushed&direction=desc&per_page=100"
        else:
            url = next_url
        response = requests.get(url, headers=headers)  # type: ignore[assignment]
        if response.status_code != 200:
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                logger.warning(
                    f"Rate limit exceeded. Retrying after {retry_after} seconds..."
                )
                time.sleep(retry_after)
                continue
            logger.warning(
                f"Failed to fetch repositories: {response.status_code} - {response.text}"
            )
            return

        repos.extend(response.json())

        next_url = None
        links = response.headers.get("Link", "").split(",")
        if not links:
            break
        for link in links:
            if 'rel="next"' in link:
                next_url = link[link.find("<") + 1 : link.find(">")]
                break
        if next_url is None:
            break

    if not repos:
        logger.info("No repositories found for user.")
        return

    # View the repositories and collect JOURNAL.md files + data
    journals = []
    for repo in repos:
        logger.debug(f"Checking repository: {repo['name']}...")
        repo_name = repo["name"]
        repo_url = repo["url"]

        response_repo = requests.get(f"{repo_url}/contents/JOURNAL.md", headers=headers)

        if response_repo.status_code not in [200, 302, 304]:
            logger.info(f"No JOURNAL.md found in repository {repo_name}")
            continue

        if response_repo.json().get("private", False):
            logger.info(f"Repository {repo_name} is private, skipping")
            continue

        journal_content = response_repo.json().get("content", "")

        # Check that it is a file and not a directory
        if response_repo.json().get("type", "") != "file":
            logger.info(f"JOURNAL.md in repository {repo_name} is not a file")
            continue

        content_encoding = response_repo.json().get("encoding", "")
        if content_encoding != "base64":
            logger.warning(
                f"Unexpected encoding for JOURNAL.md in repository {repo_name}: {content_encoding}"
            )
            continue

        journal_content_decoded = base64.b64decode(journal_content).decode("utf-8")

        # Get most recent commit date for the journal
        response_commit = requests.get(
            f"{repo_url}/commits?path=JOURNAL.md&per_page=1", headers=headers
        )
        if response_commit.status_code != 200:
            logger.warning(
                f"Failed to fetch commits for {repo_name}: {response_commit.status_code} - {response.text}"
            )
            continue
        last_updated_time = response_commit.json()[0]["commit"]["author"]["date"]
        last_updated = datetime.datetime.fromisoformat(last_updated_time)

        journal_metadata = frontmatter.loads(journal_content_decoded)

        show_on_site = journal_metadata.get("show_on_site", "False").lower() == "true"
        if not show_on_site:
            logger.info(
                f"JOURNAL.md in repository {repo_name} is not marked to show on site"
            )
            continue

        start_date = journal_metadata.get("start_date", "")

        journals.append(
            {
                "title": journal_metadata.get("title", repo_name),
                "description": journal_metadata.get("description", ""),
                "start_date": start_date,
                "image_url": "replace",
                "image_alt_text": "replace",
                "repo_url": response_repo.json().get("html_url", ""),
                "last_updated": last_updated,
                "journal_content": journal_content_decoded,
            }
        )

    # Write journals to sqlite database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS journals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            start_date TEXT,
            image_url TEXT,
            image_alt_text TEXT,
            repo_url TEXT UNIQUE,
            last_updated TIMESTAMP,
            journal_content TEXT
        )
        """
    )

    for journal in journals:
        cursor.execute(
            """
            INSERT OR REPLACE INTO journals (title, description, start_date, image_url, image_alt_text, repo_url, last_updated, journal_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                journal["title"],
                journal["description"],
                journal["start_date"],
                journal["image_url"],
                journal["image_alt_text"],
                journal["repo_url"],
                journal["last_updated"],
                journal["journal_content"],
            ),
        )

    logger.debug("Finished writing journals to database.")


# On startup, check the repositories and update the journals.
logger.debug("Fetching journals on startup...")
fetch_journals()

# Then, check the user events API and save then continue to check every X-Poll-Interval seconds specified in the response, check the user events API again for changes. If there are changes, fetch the repositories and update the journals.
while True:
    events_url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/events"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else None,
        "X-GitHub-Api-Version": "2026-03-10",
    }

    logger.debug("Checking for user events...")
    response = requests.get(events_url, headers=headers)
    if response.status_code not in [200, 304]:
        logger.warning(
            f"Failed to fetch user events: {response.status_code} - {response.text}"
        )
        continue

    if response.status_code == 200:
        logger.debug("User events changed, fetching journals...")
        fetch_journals()

    events = response.json()
    headers.update({"ETag": response.headers.get("ETag", "")})
    time.sleep(int(response.headers.get("X-Poll-Interval", 60)))
