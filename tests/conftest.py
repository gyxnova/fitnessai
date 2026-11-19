import pytest
from app.db import get_connection
from app.config import SQL_DIR



@pytest.fixture
def conn():
    conn = get_connection("fitnessai_test")

    # Safety lock: never wipe a database that isn't a test database
    if not conn.info.dbname.endswith("_test"):
        conn.close()
        pytest.fail("Database name does not end with '_test'.")

    # Clean slate
    conn.execute("DROP SCHEMA public CASCADE")
    conn.execute("CREATE SCHEMA public")

    # Rebuild tables and load test data
    for path in  sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        with open(path, "r", encoding="utf-8") as f:
            conn.execute(f.read())

    conn.commit()

    yield conn      # the test runs here
    conn.close()    # cleanup after the test