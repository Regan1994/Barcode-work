import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db"), "BACKUP_DIRECTORY": str(tmp_path / "backups"), "SECRET_KEY": "test"})


@pytest.fixture()
def client(app):
    client = app.test_client()
    with client.session_transaction() as session:
        session["admin_unlocked"] = True
    return client

