"""Entry point for `python -m gethired`."""

from gethired.cli import app


def main() -> None:
    """Invoke the CLI application."""
    app()


if __name__ == "__main__":
    main()
