# Journals Site

A site that automatically grabs `JOURNAL.md` files from my repositories and formats them into a website.

Hosted at [journal.person20020.dev](https://journal.person20020.dev/)

## Running

- Clone the repository:

```
git clone https://github.com/person20020/journals
```

### Docker

### Dev via Python

### Website

```bash
cd site
```

Create a venv and install dependencies:

```bash
python -m venv venv && . ./venv/bin/activate # or ./venv/Scripts/activate on Windows
pip install -r requirements-dev.txt
```

Run the website:

```bash
export $(grep -v '^#' .env | xargs -d '\n') && python app.py
```

### Journal fetching script

```bash
cd collector
```

Create a venv and install dependencies:

```bash
python -m venv venv && . ./venv/bin/activate # or ./venv/Scripts/activate on Windows
pip install -r requirements.txt
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
