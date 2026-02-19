from __future__ import annotations

import os
import sys


def resolve_runtime_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.getcwd())
    return os.path.dirname(os.path.abspath(__file__))


def resolve_script_path(script_name: str = "App.py") -> str:
    base_dir = resolve_runtime_base_dir()
    script_path = os.path.join(base_dir, script_name)

    if not os.path.exists(script_path):
        raise FileNotFoundError(
            f"App.py not found in runtime bundle: {script_path}"
        )

    return script_path


def main() -> None:
    # КРИТИЧНО: выключаем dev mode ДО импорта streamlit
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"

    from streamlit.web import cli as streamlit_cli

    script_path = resolve_script_path()

    sys.argv = [
        "streamlit",
        "run",
        script_path,
        "--server.headless",
        "false",
    ]

    raise SystemExit(streamlit_cli.main())


if __name__ == "__main__":
    main()
