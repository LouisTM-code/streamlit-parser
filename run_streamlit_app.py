"""Launcher script for packaging the Streamlit app as a Windows executable.

This module provides a stable entry point for PyInstaller. It starts Streamlit
programmatically with `App.py` as the target script, preserving the regular
runtime behavior of the project.
"""

from __future__ import annotations

import os
import sys


def main() -> None:
    """Run Streamlit against ``App.py``.

    The function rewrites ``sys.argv`` to emulate:

    ``streamlit run App.py --server.headless true``

    This approach keeps the app behavior equivalent to CLI startup and avoids
    issues when freezing the executable.
    """
    from streamlit.web import cli as streamlit_cli

    app_path = os.path.join(os.path.dirname(__file__), "App.py")
    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--server.headless",
        "true",
    ]
    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    main()
