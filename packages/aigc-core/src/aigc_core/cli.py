"""Command-line entry point for the AIGC studio."""

from __future__ import annotations

import typer

app = typer.Typer(help="AIGC short-drama studio CLI")


@app.callback()
def main() -> None:
    """AIGC short-drama studio."""


@app.command()
def version() -> None:
    """Print the studio version."""
    typer.echo("aigc-studio 0.1.0")


if __name__ == "__main__":
    app()
