"""Console entry point for running the Seizu ASGI server."""

import uvicorn

from reporting import settings


def main() -> None:
    """Run the Seizu web app with uvicorn."""
    uvicorn.run(
        "reporting.asgi:application",
        host=settings.HOST,
        port=settings.PORT,
        factory=False,
    )


if __name__ == "__main__":
    main()
