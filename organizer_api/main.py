"""CLI entrypoint for running the local HTTP server."""

import uvicorn
from organizer_api.app import app
from organizer_api.config import settings


def run() -> None:
    """Run local server binding to 127.0.0.1 only."""
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )


if __name__ == "__main__":
    run()
