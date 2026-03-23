# Journals Site

A site that automatically grabs `JOURNAL.md` files from my repositories and formats them into a website.

Hosted at [journal.person20020.dev](https://journal.person20020.dev/)

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
