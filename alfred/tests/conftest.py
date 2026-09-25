import sys
from pathlib import Path
import pytest

# Let tests import Alfred's modules (database, tools, ...) directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """A fresh, empty alfred.db in a temp folder — never touches the real one."""
    import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()
    return database
