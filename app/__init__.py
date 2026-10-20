from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

from config import Config
from .db import close_db, init_db
from .services import assembly_stage_label, format_datetime, format_duration, status_label


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["BACKUP_DIRECTORY"]).mkdir(parents=True, exist_ok=True)
    log_path = Path(app.config["DATABASE"]).parent / "app.log"
    if not any(isinstance(handler, RotatingFileHandler) for handler in app.logger.handlers):
        handler = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)
    app.jinja_env.globals.update(assembly_stage_label=assembly_stage_label, format_datetime=format_datetime, format_duration=format_duration, status_label=status_label)
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    from .routes import bp
    app.register_blueprint(bp)
    return app

