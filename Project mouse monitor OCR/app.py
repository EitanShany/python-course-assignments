"""Streamlit entry point for the local Mouse Monitor OCR application."""

from src.gui import render_app


def main() -> None:
    """Start the Streamlit review interface."""
    render_app()


if __name__ == "__main__":
    main()
