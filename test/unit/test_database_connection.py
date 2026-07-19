from __future__ import annotations

from src.db import database_connection as db_module


class FakeCursor:
    def __init__(self, *, rows=None, with_rows=True, lastrowid=12, rowcount=3):
        self.rows = rows or []
        self.with_rows = with_rows
        self.lastrowid = lastrowid
        self.rowcount = rowcount
        self.closed = False
        self.executed = []

    def execute(self, sql, params):
        self.executed.append((sql, params))

    def executemany(self, sql, params_list):
        self.executed.append((sql, params_list))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return 1

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self, dictionary=False):
        return self._cursor

    def commit(self):
        self.committed = True

    def is_connected(self):
        return not self.closed

    def close(self):
        self.closed = True


class FakePool:
    def __init__(self, connection):
        self.connection = connection

    def get_connection(self):
        return self.connection


def test_execute_query_returns_rows_and_closes_resources(monkeypatch):
    cursor = FakeCursor(rows=[{"value": 1}], with_rows=True)
    connection = FakeConnection(cursor)
    fake_pool = FakePool(connection)

    monkeypatch.setattr(
        db_module,
        "load_database_config",
        lambda: {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "tester",
            "password": "secret",
            "database": "fund",
            "charset": "utf8mb4",
        },
    )
    monkeypatch.setattr(
        db_module.pooling,
        "MySQLConnectionPool",
        lambda **kwargs: fake_pool,
    )

    db = db_module.DatabaseConnection()
    result = db.execute_query("SELECT 1")

    assert result == [{"value": 1}]
    assert connection.committed is True
    assert cursor.closed is True
    assert connection.closed is True


def test_insert_many_returns_rowcount(monkeypatch):
    cursor = FakeCursor(with_rows=False, rowcount=5)
    connection = FakeConnection(cursor)
    fake_pool = FakePool(connection)

    monkeypatch.setattr(
        db_module,
        "load_database_config",
        lambda: {
            "host": "127.0.0.1",
            "port": 3306,
            "user": "tester",
            "password": "secret",
            "database": "fund",
            "charset": "utf8mb4",
        },
    )
    monkeypatch.setattr(
        db_module.pooling,
        "MySQLConnectionPool",
        lambda **kwargs: fake_pool,
    )

    db = db_module.DatabaseConnection()
    affected = db.insert_many("INSERT", [(1,), (2,)])

    assert affected == 5
    assert connection.committed is True
    assert cursor.closed is True
