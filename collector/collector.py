import base64
import logging
import os
import signal
import sqlite3
import sys
import time

import frontmatter
import requests

IS_DEV = os.getenv("DEV", "False").lower() == "true"

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")
if not GITHUB_USERNAME:
    raise ValueError("GITHUB_USERNAME environment variable is required")

GITHUB_API_URL = "https://api.github.com"

DB_PATH = "/app/data/journals.db" if not IS_DEV else "../journals.db"

logging.basicConfig(
    level=logging.DEBUG if IS_DEV else logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

logger.info("Starting journal collector...")


shutdown = False


def signal_handler(sig, frame):
    global shutdown
    logger.info("Shutdown signal received, exiting...")
    shutdown = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


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

        try:
            response = requests.get(url, headers=headers, timeout=10)  # type: ignore
        except Exception as e:
            logging.warning(f"Failed to fetch repositories list: {e}")
            return False

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

        try:
            response_repo = requests.get(
                f"{repo_url}/contents/JOURNAL.md", headers=headers, timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to fetch repository '{repo_name}': {e}")
            continue

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
        last_updated = "0001-01-01T12:00:00Z"
        try:
            response_commit = requests.get(
                f"{repo_url}/commits?path=JOURNAL.md&per_page=1",
                headers=headers,
                timeout=10,
            )
            if response_commit.status_code != 200:
                logger.warning(
                    f"Failed to fetch commits for {repo_name}: {response_commit.status_code} - {response.text}"
                )
            last_updated = response_commit.json()[0]["commit"]["author"]["date"]

        except Exception as e:
            logger.warning(
                f"Failed to fetch commits for repository '{repo_name}'. Skipping last_updated: {e}"
            )

        journal = frontmatter.loads(journal_content_decoded)

        show_on_site = journal.get("show_on_site", False)
        if not show_on_site:
            logger.info(
                f"JOURNAL.md in repository {repo_name} is not marked to show on site"
            )
            continue

        start_date = journal.get("start_date", "")

        journals.append(
            {
                "title": journal.get("title", repo_name),
                "description": journal.get("description", ""),
                "start_date": start_date,
                "image_url": journal.get("image_url", ""),
                "image_alt_text": journal.get("image_alt_text", ""),
                "repo_url": repo_url,
                "last_updated": last_updated  # type: ignore
                if "last_updated" in dir()
                else "0001-01-01T12:00:00Z",
                "path": "/journals/" + repo_name,
                "journal_content": journal.content,
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
            last_updated TEXT,
            path TEXT,
            journal_content TEXT
        )
        """
    )

    for journal in journals:
        cursor.execute(
            """
            INSERT OR REPLACE INTO journals (title, description, start_date, image_url, image_alt_text, repo_url, last_updated, path, journal_content)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                journal["title"],
                journal["description"],
                journal["start_date"],
                journal["image_url"],
                journal["image_alt_text"],
                journal["repo_url"],
                journal["last_updated"],
                journal["path"],
                journal["journal_content"],
            ),
        )

    current_repo_urls = [journal["repo_url"] for journal in journals]
    if current_repo_urls:
        cursor.execute(
            f"""
            DELETE FROM journals
            WHERE repo_url NOT IN ({",".join("?" for _ in current_repo_urls)})
            """,
            current_repo_urls,
        )

    conn.commit()
    conn.close()

    logger.debug("Finished writing journals to database.")


# On startup, check the repositories and update the journals.
logger.debug("Fetching journals on startup...")
fetch_journals()

# Then, poll the events API for changes.
events_url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/events"
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else None,
    "X-GitHub-Api-Version": "2026-03-10",
}

while not shutdown:
    try:
        logger.debug("Checking for user events...")

        try:
            response = requests.get(events_url, headers=headers, timeout=10)
        except Exception as e:
            logger.warning(f"Failed to check user events: {e}")
            continue

        if response.status_code not in [200, 304]:
            logger.warning(
                f"Failed to fetch user events: {response.status_code} - {response.text}"
            )
            continue

        if response.status_code == 200:
            poll_interval = int(response.headers.get("X-Poll-Interval", 60))
            headers["If-None-Match"] = response.headers.get("ETag", "")
            events = response.json()
            relevant_events = {
                "CreateEvent",
                "DeleteEvent",
                "PublicEvent",
                "PushEvent",
            }
            if any(event["type"] in relevant_events for event in events):
                logger.debug("User events changed, fetching journals...")
                fetch_journals()
        else:
            logger.debug("No changes in user events.")

        sleep_time = 0
        while sleep_time < (poll_interval if "poll_interval" in locals() else 60):  # type: ignore
            if shutdown:
                exit(0)
            time.sleep(1)
            sleep_time += 1

    except Exception as e:
        logger.warning(f"Error in main loop: {e}")
