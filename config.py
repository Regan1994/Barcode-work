from pathlib import Path
import os
import sys


if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent

INSTANCE_DIR = Path(os.environ.get("INTJR_DATA_DIR", BASE_DIR / "instance"))
DATABASE_PATH = INSTANCE_DIR / "intjr.db"
BACKUP_DIR = INSTANCE_DIR / "backups"


class Config:
    SECRET_KEY = os.environ.get("INTJR_SECRET_KEY", "intjr-local-development-key")
    INITIAL_ACCESS_PASSWORD = "TJR"
    DATABASE = str(DATABASE_PATH)
    BACKUP_DIRECTORY = str(BACKUP_DIR)
    HOST = "127.0.0.1"
    PORT = int(os.environ.get("INTJR_PORT", "5000"))

