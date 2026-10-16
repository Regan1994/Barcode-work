import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.services import backup_database
from config import Config


app = create_app()
with app.app_context():
    print(backup_database(Config.BACKUP_DIRECTORY))

