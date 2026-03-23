import os
from app import create_app

app = create_app()


def _get_port(default=5050):
    raw_port = os.environ.get("PORT") or os.environ.get("FLASK_PORT")
    if not raw_port:
        return default
    try:
        return int(raw_port)
    except ValueError:
        return default


def _get_debug(default=True):
    raw_debug = os.environ.get("FLASK_DEBUG")
    if raw_debug is None:
        return os.environ.get("FLASK_ENV", "dev") == "dev"
    return raw_debug.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = _get_port(default=5050)
    debug = _get_debug(default=True)

    app.run(debug=debug, host=host, port=port)
