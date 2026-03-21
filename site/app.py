import logging
import os

import flask

PLAUSIBLE_SRC_URL = os.getenv("PLAUSIBLE_SRC_URL", "")
PLAUSIBLE_DATA_API = os.getenv("PLAUSIBLE_DATA_API", "")
PLAUSIBLE_DOMAIN = os.getenv("PLAUSIBLE_DOMAIN", "")

GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

IS_DEV = os.getenv("FLASK_ENV") == "development"

logging.basicConfig(
    level=logging.INFO if IS_DEV else logging.WARNING,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = flask.Flask(__name__)
if IS_DEV:
    from flask_sock import Sock

    sock = Sock(app)


JOURNALS_DIR = os.path.realpath(os.path.join(app.root_path, "templates", "journals"))


def get_journals():
    """Get a list of dicts of journals with keys: title, description, last_updated, url, image_url, and repo_url"""
    journals = []
    for i in range(5):
        journals.append({
            "title": f"Example Project {i}",
            "description": "This is an example description. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.",
            "last_updated": "2024-01-01",
            "url": "/journals/example-journal",
            "image_url": "https://placehold.co/400x200",
            "repo_url": f"https://github.com/{GITHUB_USERNAME}/example-journal",
        })
    return journals


# Flask
@app.context_processor
def inject_globals():
    return {
        "IS_DEV": IS_DEV,
        "PLAUSIBLE_SRC_URL": PLAUSIBLE_SRC_URL,
        "PLAUSIBLE_DATA_API": PLAUSIBLE_DATA_API,
        "PLAUSIBLE_DOMAIN": PLAUSIBLE_DOMAIN,
        "GITHUB_USERNAME": GITHUB_USERNAME,
    }


@app.route("/")
def index():
    return flask.render_template("index.html", journals=get_journals())


# Project journals
@app.route("/journals/<path:path>")
def journal_pages(path):
    try:
        full_path = flask.safe_join(JOURNALS_DIR, path)
    except Exception:
        flask.abort(404)

    real_path = os.path.realpath(full_path)  # type: ignore[possibly-undefined]

    # Check that path is inside the journals directory
    if not real_path.startswith(JOURNALS_DIR + os.sep):
        flask.abort(404)

    # Check that the file exists
    if not os.path.isfile(real_path):
        flask.abort(404)

    return flask.render_template(f"journals/{path}")


# Auto reload websocket
if IS_DEV:
    @sock.route("/ws/auto-reload")  # type: ignore[possibly-undefined]
    def auto_reload_ws(ws):
        while True:
            ws.receive()


@app.errorhandler(404)
def not_found(e):
    return flask.render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
