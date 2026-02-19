"""Executable launcher for starting the Streamlit application from a frozen build.

Module purpose:
    Provide a robust entry point for PyInstaller builds (including ``--onefile``),
    where source files are unpacked into a temporary directory at runtime.

Why this approach:
    Streamlit CLI requires a physical target script path. In ``--onefile`` mode,
    relying on ``__file__`` points to a temporary bootstrap location and may miss
    project files unless they are explicitly included as data. This module resolves
    the target path from PyInstaller runtime metadata and then delegates execution
    to the official Streamlit CLI.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StreamlitExecutableLauncher:
    """Launcher that prepares CLI arguments and starts Streamlit.

    Attributes:
        script_name: Relative filename of the Streamlit target script.

    Encapsulation:
        Path resolution and argument construction are hidden inside private methods,
        while ``run`` provides the single public behavior.
    """

    script_name: str = "App.py"

    def run(self) -> None:
        """Execute Streamlit with a resolved target script path.

        Raises:
            FileNotFoundError: If target script is not available in runtime bundle.
            SystemExit: Propagated from Streamlit CLI main function.
        """
        from streamlit.web import cli as streamlit_cli

        script_path = self._resolve_script_path()
        sys.argv = self._build_cli_arguments(script_path)
        raise SystemExit(streamlit_cli.main())

    def _resolve_script_path(self) -> str:
        """Resolve absolute path to the Streamlit target script.

        Returns:
            Absolute filesystem path to ``App.py``.

        Raises:
            FileNotFoundError: If ``App.py`` was not bundled into executable data.
        """
        base_dir = self._resolve_runtime_base_dir()
        script_path = os.path.join(base_dir, self.script_name)

        if not os.path.exists(script_path):
            raise FileNotFoundError(
                "Target Streamlit script is missing in runtime bundle: "
                f"{script_path}. Ensure PyInstaller includes App.py via --add-data."
            )

        return script_path

    @staticmethod
    def _resolve_runtime_base_dir() -> str:
        """Get runtime base directory for source and frozen modes.

        Returns:
            Runtime directory containing bundled data files.

        Notes:
            - In PyInstaller one-file/one-dir builds, ``sys._MEIPASS`` points to the
              extraction directory with ``--add-data`` files.
            - In normal source execution, fallback to the current module directory.
        """
        if getattr(sys, "frozen", False):
            return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.dirname(os.path.abspath(__file__))

    @staticmethod
    def _build_cli_arguments(script_path: str) -> list[str]:
        """Build argument vector equivalent to Streamlit CLI invocation.

        Args:
            script_path: Absolute path to Streamlit target script.

        Returns:
            CLI argument list equivalent to:
            ``streamlit run <script_path> --server.headless true``.
        """
        return [
            "streamlit",
            "run",
            script_path,
            "--server.headless",
            "true",
        ]


def main() -> None:
    """Application entry point for executable and source runs."""
    StreamlitExecutableLauncher().run()


if __name__ == "__main__":
    main()
