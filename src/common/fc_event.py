import json
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger(__name__)

def _to_dict_from_bytes_or_str(raw: Any) -> Dict[str, Any]:
    """将 bytes/str 尝试解析为 dict；解析失败返回空 dict。"""
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode('utf-8', errors='ignore')
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return raw if isinstance(raw, dict) else {}

def parse_fc_event(event: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    统一解析阿里云 FC 的 event 入参，返回 (evt, payload) 两个字典：
    - evt：解析后的完整事件对象（dict）
    - payload：业务负载（dict），若事件没有 payload 字段，则将整个 evt 当作 payload
    """
    # 先把 event 统一成 dict
    evt = _to_dict_from_bytes_or_str(event)
    if not isinstance(evt, dict):
        logger.warning("event 不是 dict/str/bytes，可用信息有限，已置为空字典")
        evt = {}

    # 兼容两种传参：
    # 1) {"payload": "{...json...}"} 或 {"payload": {...}}
    # 2) 直接就是 payload 内容
    payload = evt.get('payload', evt)

    # 再把 payload 也统一成 dict
    payload = _to_dict_from_bytes_or_str(payload)
    if not isinstance(payload, dict):
        logger.error("payload 解析失败，置为空字典")
        payload = {}

    return evt, payload