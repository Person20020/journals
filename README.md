# Journals Site

A site that automatically grabs `JOURNAL.md` files from my repositories and formats them into a website.

Hosted at [journal.person20020.dev](https://journal.person20020.dev/)

## Running

- Clone the repository:

```
git clone https://github.com/person20020/journals && cd journals
```

### Docker

Fill in the environment variables in the docker-compose.yaml.

```yaml
services:
  web:
    environment:
      - PLAUSIBLE_SRC_URL=  # Optional for analytics
      - PLAUSIBLE_DATA_API=  # Optional for analytics
      - PLAUSIBLE_DOMAIN=  # Optional for analytics
      - GITHUB_USERNAME=  # Used to link to your profile in the footer. If left empty the footer will show 'Made by @Person20020' instead
  collector:
    environment:
      - GITHUB_USERNAME=  # Required
      - GITHUB_TOKEN=  # Required
```

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

Create a .env file with the necessary variables in site/:

```bash
DEV=True
GITHUB_USERNAME=yourusername
```

Run the website:

```bash
export $(grep -v '^#' .env | xargs -d '\n') && python app.py
```

### Journal fetching script

Create a venv and install dependencies:

```bash
cd collector
python -m venv venv && . ./venv/bin/activate # or ./venv/Scripts/activate on Windows
pip install -r requirements.txt
```

Create a .env file with the necessary variables in site/:

```bash
DEV=True
GITHUB_USERNAME=YourUsername
GITHUB_TOKEN=github_pat_your_token
```

Start the script:

```bash
export $(grep -v '^#' .env | xargs -d '\n') && python collector.py
```

<!--
### Run normally via the docker container:
```bash
docker build -t journals-site .
docker run journals-site
```

### Run in dev mode via python:

- Create venv
```bash
python -m venv venv
```

- Activate it

On Linux/Mac:
```bash
source ./venv/bin/activate
```

Or for Windows:
```bash
./venv/Scripts/activate
```

- Install requirements,

```bash
pip install -r requirements-dev.txt
```

(This includes flask_sock for auto reload)

```bash
python app.py
```-->
