import datetime
import logging
import os
import sqlite3

import flask  # type: ignore
import markdown  # type: ignore
import markupsafe  # type: ignore

PLAUSIBLE_SRC_URL = os.getenv("PLAUSIBLE_SRC_URL", "")
PLAUSIBLE_DATA_API = os.getenv("PLAUSIBLE_DATA_API", "")
PLAUSIBLE_DATA_DOMAIN = os.getenv("PLAUSIBLE_DATA_DOMAIN", "")

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

IS_DEV = os.getenv("DEV", "False").lower() == "true"

DB_PATH = "/app/data/journals.db" if not IS_DEV else os.path.abspath("../journals.db")

logging.basicConfig(
    level=logging.DEBUG if IS_DEV else logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Check if the database file exists
if not os.path.exists(DB_PATH):
    logger.error(f"Database file not found at {DB_PATH}. Please make sure it exists.")
    raise FileNotFoundError(f"Database file not found at {DB_PATH}")

app = flask.Flask(__name__)
if IS_DEV:
    try:
        from flask_sock import Sock  # type: ignore

        sock = Sock(app)
    except ImportError as e:
        raise ImportError(
            f"Failed to import Sock from flask_sock. Make sure to install the requirements-dev.txt or disable the DEV env variable: {e}"
        )


journals_db_fields = [
    "title",
    "description",
    "start_date",
    "image_url",
    "image_alt_text",
    "repo_url",
    "last_updated",
    "path",
    "journal_content",
]


def get_journals(path="") -> dict[str, str] | list[dict[str, str]] | bool:
    """Get a list of dicts of journals with keys: title, description, last_updated, url, image_url, and repo_url"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            SELECT {", ".join(journals_db_fields)} FROM journals {"WHERE path = ?" if path else ""} ORDER BY last_updated DESC
            """,
            (f"/journals/{path}",) if path else (),
        )
        if path:
            row = cursor.fetchone()
            if not row:
                return False
            journal = {}
            for i, field in enumerate(journals_db_fields):
                journal[field] = row[i]
            return journal
        else:
            journals = []
            for i, row in enumerate(cursor.fetchall()):
                journal = {}
                for i, field in enumerate(journals_db_fields):
                    journal[field] = row[i]
                journals.append(journal)

    return journals


# Flask
@app.context_processor
def inject_globals():
    return {
        "IS_DEV": IS_DEV,
        "PLAUSIBLE_SRC_URL": PLAUSIBLE_SRC_URL,
        "PLAUSIBLE_DATA_API": PLAUSIBLE_DATA_API,
        "PLAUSIBLE_DATA_DOMAIN": PLAUSIBLE_DATA_DOMAIN,
        "GITHUB_USERNAME": GITHUB_USERNAME,
    }


@app.route("/")
def index():
    journals = get_journals()
    for journal in journals:  # type: ignore
        journal["last_updated"] = datetime.datetime.fromisoformat(  # type: ignore
            journal["last_updated"]  # type: ignore
        ).strftime("%B %d, %Y")
    return flask.render_template("index.html", journals=journals)


# Project journals
@app.route("/journals/<path>")
def journal_pages(path):
    journal = get_journals(path)
    if not journal:
        flask.abort(404)
    journal["journal_content"] = (  # type: ignore
        markupsafe.Markup(
            markdown.markdown(
                journal["journal_content"],  # type: ignore
                extensions=[
                    "fenced_code",
                    "tables",
                    "toc",
                    "codehilite",
                    "nl2br",
                    "footnotes",
                    "def_list",
                    "admonition",
                    "sane_lists",
                ],
            )
        )
    )
    journal["last_updated"] = datetime.datetime.fromisoformat(  # type: ignore
        journal["last_updated"]  # type: ignore
    ).strftime("%B %d, %Y")

    return flask.render_template("journal.html", journal=journal)


@app.route("/health")
def health():
    return flask.Response("OK", status=200, mimetype="text/plain")


# Auto reload websocket
if IS_DEV:

    @sock.route("/ws/auto-reload")  # type: ignore
    def auto_reload_ws(ws):
        while True:
            ws.receive()


@app.errorhandler(404)
def not_found(e):
    return flask.render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
