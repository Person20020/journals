import logging
import os
import time

import requests

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
SCRAPE_INTERVAL = int(os.getenv("SCRAPE_INTERVAL", "3600"))

if not GITHUB_USERNAME:
    raise ValueError("GITHUB_USERNAME environment variable is required")

GITHUB_API_URL = "https://api.github.com"

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def scrape_repos():
    # Get user's repositories
    url = f"{GITHUB_API_URL}/users/{GITHUB_USERNAME}/repos"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_TOKEN}" if GITHUB_TOKEN else None,
        "X-GitHub-Api-Version": "2026-03-10",
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.warning(f"Failed to fetch repositories: {response.status_code} - {response.text}")
        return

    # View the repositories and collect JOURNAL.md files
