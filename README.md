# Journals Site

A site that automatically grabs `JOURNAL.md` files from my repositories and formats them into a website.

Hosted at [journal.person20020.dev](https://journal.person20020.dev/)

## Using the Site

For a journal to show on the site it must have `show_on_site: True` in the frontmatter. Here is a list of the fields that it should have:

```yaml
---
show_on_site: True
title: "Journal/project title" # If this isn't set the repo name will be used instead.
description: "A description of the project." # If not set it will be left blank.
start_date: "yyyy-mm-dd" # The start date of the project. If not set it defaults to 0001-01-01.
image_url: "https://example.com/image_url" # A cover image for the journal
image_alt_text: "An image of my finished project" # Alt text for the cover image
---
```

Some other info is automatically filled generated:

```yaml
last_updated: # Used to sort journals by latest on the home page and also displayed on the journal.
path: # Generated with '/journal/{repo_name}'
journal_content: # The content of the journal. Only the root directory of the repository is searched for a JOURNAL.md file. (Currently it is case sensitive but I will fix that.)
```

Every ~minute the GitHub user events API is checked for changes. When a change is found all repositories will be checked so it may take several minutes to update on the site. (Hopefully I will change this soon.)

## Running

- Clone the repository:

```
git clone https://github.com/person20020/journals && cd journals
```

Fill in environment variables in .env:

```bash
GITHUB_USERNAME=YourUsername
GITHUB_TOKEN=github_pat_your_token
PLAUSIBLE_SRC_URL=  # Optional
PLAUSIBLE_DATA_API=  # Optional
PLAUSIBLE_DATA_DOMAIN=  # Optional
DEV= # Set true for dev
```

### Docker

Start the containers:

```bash
docker compose up -d
```

### Dev via Python

### Website

Create a venv and install dependencies:

```bash
cd site
python -m venv venv && . ./venv/bin/activate # or ./venv/Scripts/activate on Windows
pip install -r requirements-dev.txt
```

Run the website:

```bash
export $(grep -v '^#' ../.env | xargs -d '\n') && python app.py
```

### Journal fetching script

Create a venv and install dependencies:

```bash
cd collector
python -m venv venv && . ./venv/bin/activate # or ./venv/Scripts/activate on Windows
pip install -r requirements.txt
```

Start the script:

```bash
export $(grep -v '^#' ../.env | xargs -d '\n') && python collector.py
```
