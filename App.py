import argparse
from Parse import WebParser
from web_ui import StreamlitUI

def main():
    parser = WebParser()
    
    is_streamlit_running()
    ui = StreamlitUI(parser)
    ui.run()

def is_streamlit_running() -> bool:
    """Проверка запущен ли Streamlit"""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx() is not None
    except ImportError:
        return False

if __name__ == "__main__":
    main()