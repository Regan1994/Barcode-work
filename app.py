import sys
import threading
import time
import webbrowser

from app import create_app
from config import Config


app = create_app()


def open_browser():
    time.sleep(1)
    webbrowser.open(f"http://{Config.HOST}:{Config.PORT}")


if __name__ == "__main__":
    if getattr(sys, "frozen", False):
        threading.Thread(target=open_browser, daemon=True).start()
    app.run(host=Config.HOST, port=Config.PORT, debug=False, use_reloader=False)

