import os, sys
import threading
import time
from src.API.登录接口.login import login, login_passport, inference_passport_for_bind
from src.service.银行卡账户.bankAccoutService import getMaxhqbBank
from src.common.logger import get_logger

_cache_lock = threading.Lock()
_user_cache = {}
_CACHE_TTL_SEC = 1800
logger = get_logger(__name__)

def _get_cached_user(account: str, password: str):
    key = (account, password)
    with _cache_lock:
        entry = _user_cache.get(key)
        if not entry:
            return None
        if time.time() - entry[1] > _CACHE_TTL_SEC:
            _user_cache.pop(key, None)
            return None
        return entry[0]

def _set_user_cache(user):
    key = (getattr(user, "account", None), getattr(user, "password", None))
    if not all(key):
        return
    with _cache_lock:
        _user_cache[key] = (user, time.time())

def invalidate_user_cache(account: str, password: str):
    key = (account, password)
    with _cache_lock:
        _user_cache.pop(key, None)

def get_user_all_info(account: str, password: str):
    cached = _get_cached_user(account, password)
    if cached is not None:
        logger.info("用户信息命中缓存", extra={"account": account})
        return cached
    user = login(account, password)
    if not user:
        logger.error("登录失败", extra={"account": account})
        return None
    user = inference_passport_for_bind(user)
    if not user:
        logger.error("passport推断失败", extra={"account": account})
        return None
    user = getMaxhqbBank(user)
    if user:
        _set_user_cache(user)
        logger.info("完成用户信息聚合", extra={"account": account})
    return user

def refresh_user_tokens(account: str, password: str):
    user = _get_cached_user(account, password)
    if not user:
        return get_user_all_info(account, password)
    u1 = login_passport(user)
    if not u1:
        invalidate_user_cache(account, password)
        return get_user_all_info(account, password)
    u2 = inference_passport_for_bind(u1)
    if not u2:
        invalidate_user_cache(account, password)
        return get_user_all_info(account, password)
    _set_user_cache(u2)
    return u2
