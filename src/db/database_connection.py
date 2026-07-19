from __future__ import annotations

import os

from mysql.connector import Error, pooling

from src.common.app_config import ConfigError, load_database_config
from src.common.logger import get_logger


logger = get_logger(__name__)


class DatabaseConnection:
    """MySQL connection-pool wrapper used by repositories and scheduled task services."""

    def __init__(self, pool_size: int = 10):
        self.pool_size = pool_size
        self.dbconfig = load_database_config()
        self.connection_pool = None
        self.pool_name = f"fund_system_pool_{os.getpid()}_{id(self)}"

    def create_pool(self):
        """Lazily create the connection pool so import-time side effects stay small."""
        if self.connection_pool is None:
            try:
                self.connection_pool = pooling.MySQLConnectionPool(
                    pool_name=self.pool_name,
                    pool_size=self.pool_size,
                    pool_reset_session=True,
                    **self.dbconfig,
                )
                logger.info("数据库连接池创建成功", extra={"action": "db_pool_create"})
            except ConfigError:
                raise
            except Error as exc:
                raise ConnectionError(f"创建连接池失败: {exc}") from exc
        return self.connection_pool

    def get_connection(self):
        pool = self.create_pool()
        return pool.get_connection()

    def disconnect(self, conn):
        if conn and conn.is_connected():
            conn.close()

    def test_connection(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            self.disconnect(conn)
            logger.info("数据库连接池测试成功", extra={"action": "db_pool_test"})
            return True
        except Error as exc:
            logger.error("测试连接失败: %s", exc, extra={"action": "db_pool_test"})
            return False

    def execute_query(self, sql, params=None):
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, params or ())
            result = cursor.fetchall() if cursor.with_rows else []
            conn.commit()
            return result
        finally:
            if cursor is not None:
                cursor.close()
            self.disconnect(conn)

    def insert(self, sql, params=None):
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor.lastrowid
        finally:
            if cursor is not None:
                cursor.close()
            self.disconnect(conn)

    def insert_many(self, sql, params_list=None):
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list or [])
            conn.commit()
            return cursor.rowcount
        finally:
            if cursor is not None:
                cursor.close()
            self.disconnect(conn)

    def update(self, sql, params=None):
        conn = self.get_connection()
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params or ())
            conn.commit()
            return cursor.rowcount
        finally:
            if cursor is not None:
                cursor.close()
            self.disconnect(conn)

    def delete(self, sql, params=None):
        return self.update(sql, params)
