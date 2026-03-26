"""Streamlit script entrypoint.

Role and responsibility:
    - start Streamlit UI runtime for parser application.

Boundaries:
    - does not compose parser internals;
    - does not implement parsing workflows.

Interactions:
    - delegates startup to ``web_ui.run_streamlit_ui``.
"""

from web_ui import run_streamlit_ui


def main() -> None:
    """Launch Streamlit UI entrypoint."""
    run_streamlit_ui()


if __name__ == "__main__":
    main()
