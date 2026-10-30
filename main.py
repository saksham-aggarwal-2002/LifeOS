"""Entry point: `python main.py` opens the LifeOS window."""
from pathlib import Path

import webview

from app import datafolder
from app.api import Api

# resolve(): inside LifeOS.app this file is reached through a symlink.
UI_DIR = Path(__file__).resolve().parent / "ui"


def main():
    conn = datafolder.start()  # your LifeOS_data, or the test folder (chosen in Settings)

    webview.create_window(
        "LifeOS",
        str(UI_DIR / "index.html"),
        js_api=Api(conn),
        width=1280,
        height=800,
        min_size=(1000, 600),
    )
    webview.start()


if __name__ == "__main__":
    main()
