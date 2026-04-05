import base64
import logging
import os
import signal
import sqlite3
import sys
import time

import frontmatter  # type: ignore
import requests  # type: ignore

IS_DEV = os.getenv("DEV", "False").lower() == "true"

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable is required")
if not GITHUB_USERNAME:
    raise ValueError("GITHUB_USERNAME environment variable is required")

GITHUB_API_URL = "https://api.github.com"

DB_PATH = "/app/data/journals.db" if not IS_DEV else "../journals.db"

REQUEST_TIMEOUT = 10

logging.basicConfig(
    level=logging.DEBUG if IS_DEV else logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

logger.info("Starting journal collector...")


def signal_handler(sig, frame):
    logger.info("Shutdown signal received, exiting...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def update_journals(fetch_repo_name=None):
    """Update journals database. If repo is set update only that repository."""
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "X-GitHub-Api-Version": "2026-03-10",
    }

    repos = []
    # If checking single repo
    if fetch_repo_name:
        repos.append({"name": fetch_repo_name})

    # Fetch repo list
    else:
        first_loop = True
        while True:
            if first_loop:
                url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/repos?type=owner&sort=pushed&direction=desc&per_page=100"

            try:
                response = requests.get(
                    url,  # type: ignore
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
            except Exception as e:
                logging.error(f"Failed to fetch repositories list: {e}")
                return False

            if response.status_code != 200:
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(
                        f"Rate limited. Retrying after {retry_after} seconds."
                    )
                    time.sleep(retry_after)
                    continue  # Retry

                logger.warning(
                    f"Failed to fetch repositories: {response.status_code} - {response.text}"
                )
                return False

            repos.extend(response.json())  # Add repositories onto repo list

            # Get next url if response is paginated
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
            url = next_url

    # Check repositories and collect journal files + data
    journals = []
    for repo in repos:
        logger.debug(f"Checking repository: {repo['name']}...")
        repo_name = repo["name"]
        repo_url = f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}"

        # Fetch the repository tree to find the journal file
        try:
            response = requests.get(
                f"{repo_url}/git/trees/HEAD?recursive=1",
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as e:
            logger.warning(f"Failed to fetch repository '{repo_name}': {e}")
            continue
        if response.status_code not in [200, 302, 304]:
            if not response.status_code == 409:  # Repository is empty, don't log as warning
                logger.warning(
                    f"Failed to fetch tree for repository '{repo_name}': {response.status_code} - {response.text}"
                )
            continue

        file_url = None
        for file in response.json().get("tree", []):
            if file["path"].lower().find("journal") != -1 and file["path"].endswith(
                ".md"
            ):
                file_url = file["url"]
                break

        if not file_url:
            if response.json().get("truncated", False):
                logger.warning(
                    f"Repository '{repo_name}' tree is truncated, only checking top level files for journal"
                )
                response = requests.get(
                    f"{GITHUB_API_URL}/repos/{GITHUB_USERNAME}/{repo_name}/contents",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                if response.status_code not in [200, 302, 304]:
                    logger.warning(
                        f"Failed to fetch contents for repository '{repo_name}': {response.status_code} - {response.text}"
                    )
                    continue

                for file in response.json():
                    if file["path"].lower().find("journal") != -1 and file[
                        "path"
                    ].endswith(".md"):
                        file_url = file["url"]
                        break

        if not file_url:
            logger.debug(f"No journal found in repository {repo_name}")
            continue

        # Get journal file content
        try:
            repo_response = requests.get(
                file_url,  # type: ignore
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
        except Exception as e:
            logger.warning(
                f"Failed to fetch journal from repository '{repo_name}': {e}"
            )
            continue
        if repo_response.status_code not in [200, 302, 304]:
            logger.warning(
                f"Failed to fetch journal for repository '{repo_name}': {response.status_code} - {response.text}"
            )
            continue

        encoded_journal = repo_response.json().get("content", "")
        if not encoded_journal:
            logger.warning(f"Journal file in repository '{repo_name}' is empty")
            continue

        encoding = repo_response.json().get("encoding", "")
        if encoding == "base64":
            try:
                decoded_journal = base64.b64decode(encoded_journal).decode("utf-8")
            except Exception as e:
                logger.warning(
                    f"Failed to decode journal content for repository '{repo_name}': {e}"
                )
                continue
        elif encoding == "utf-8":
            decoded_journal = encoded_journal
        else:
            logger.warning(
                f"Unknown encoding '{encoding}' for journal in repository '{repo_name}'"
            )
            continue

        # Get commit date for the journal file
        last_updated = "0001-01-01T00:00:00Z"
        try:
            commits_response = requests.get(
                f"{repo_url}/commits?path={file['path']}&per_page=1",  # type: ignore
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if commits_response.status_code not in [200, 302, 304]:
                logger.warning(
                    f"Failed to fetch commits for repository '{repo_name}'. Using default date for last_updated: {commits_response.status_code} - {commits_response.text}"
                )
            else:
                commits = commits_response.json()
                if commits:
                    last_updated = (
                        commits[0]
                        .get("commit", {})
                        .get("committer", {})
                        .get("date", last_updated)
                    )
        except Exception as e:
            logger.warning(
                f"Failed to fetch commits for repository '{repo_name}'. Using default date for last_updated: {e}"
            )

        journal = frontmatter.loads(decoded_journal)

        if not journal.get("show_on_site", False):
            logger.debug(
                f"Journal in repository '{repo_name}' is not marked as show_on_site, skipping"
            )
            if fetch_repo_name:
                remove_journal(repo_name)
            continue

        journals.append(
            {
                "title": journal.get("title", repo_name),
                "description": journal.get("description", ""),
                "start_date": journal.get("start_date", ""),
                "image_url": journal.get("image_url", ""),
                "image_alt_text": journal.get("image_alt_text", ""),
                "repo_url": f"https://github.com/{GITHUB_USERNAME}/{repo_name}",
                "last_updated": last_updated,
                "path": f"/journals/{repo_name}",
                "journal_content": journal.content,
            }
        )

    # Write journals to database
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

    # Clear journals not marked for the site
    if not fetch_repo_name:
        current_repo_urls = [journal["repo_url"] for journal in journals]
        if current_repo_urls:
            cursor.execute(
                f"""
                DELETE FROM journals WHERE repo_url NOT IN ({",".join("?" for _ in current_repo_urls)})
                """,
                current_repo_urls,
            )

    conn.commit()
    conn.close()

    logger.debug("Finished writing journals to database.")
    return True


def remove_journal(repo_name):
    """Remove journal from database based on repo name"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM journals WHERE repo_url = ?
        """,
        (f"https://github.com/{GITHUB_USERNAME}/{repo_name}",)
    )
    conn.commit()
    conn.close()


# Update all journals on startup
logger.debug("Updating journals on startup...")
update_journals()

# Poll the events API for changes
events_url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/events"
headers = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2026-03-10",
}

poll_interval = 60
while True:
    try:
        logger.debug("Checking for user events...")

        try:
            response = requests.get(
                events_url, headers=headers, timeout=REQUEST_TIMEOUT
            )
        except Exception as e:
            logger.warning(f"Failed to check user events: {e}")
            continue

        if response.status_code not in [200, 304]:
            logger.warning(
                f"Failed to check user events: {response.status_code} - {response.text}"
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
            update_repos = []
            for event in events:
                if event["type"] in relevant_events:
                    repo_name = event.get("repo", {}).get("name", "").split("/")[1]
                    if not repo_name or repo_name in update_repos:
                        continue
                    logger.debug(
                        f"New user event, updating journal for repo '{repo_name}'"
                    )
                    if event["type"] == "DeleteEvent":
                        logger.debug(
                            f"Repository deleted event, removing journal for repo '{repo_name}'"
                        )
                        remove_journal(repo_name)
                        continue
                    update_journals(repo_name)
                    update_repos.append(repo_name)

        sleep_time = 0
        while sleep_time < poll_interval:
            time.sleep(1)
            sleep_time += 1

    except (KeyboardInterrupt, SystemExit):
        logger.debug("Stopping")
        sys.exit(0)

    except Exception as e:
        logger.warning(f"Error in main loop: {e}")
