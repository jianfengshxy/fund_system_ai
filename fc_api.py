"""
FC HTTP 入口壳子。

根目录文件仅保留函数计算需要的默认入口，
实际 HTTP 处理逻辑统一放到 `src/web_api` 目录中，便于按功能模块维护。
"""

from src.web_api.fc_http_handler import handler

__all__ = ["handler"]
