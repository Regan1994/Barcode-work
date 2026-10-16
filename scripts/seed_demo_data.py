import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from app.db import get_db
from app.services import create_machine_range, create_model


app = create_app()
with app.app_context():
    db = get_db()
    existing = db.execute("SELECT COUNT(*) AS n FROM model_master").fetchone()["n"]
    if existing == 0:
        for name, code in (("HR-255", "HR255"), ("FAR-210", "FAR210"), ("RC-210", "RC210")):
            model_id = create_model(name, code, "可刪除或停用的示例機型", "seed")
            if code == "HR255":
                create_machine_range(model_id, "E", 1, 10, 2, "unknown", "seed")
        print("demo data created; machine semantics remain unknown")
    else:
        print("demo data skipped: model_master is not empty")

