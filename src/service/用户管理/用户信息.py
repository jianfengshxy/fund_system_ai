import os, sys
import threading
import time
import json
from pathlib import Path
from src.API.登录接口.login import login, login_passport, inference_passport_for_bind
from src.service.银行卡账户.bankAccoutService import getMaxhqbBank
from src.common.logger import get_logger
from src.common.constant import DEFAULT_USER
from src.service.用户管理.user_token_store import UserTokenStore

_cache_lock = threading.Lock()
_user_cache = {}
_CACHE_TTL_SEC = 1800
_FILE_CACHE_TTL_SEC = 86400
_FILE_CACHE_PATH = Path(__file__).resolve().parent / 'user_cache.json'
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

def _ensure_bank(user):
    try:
        has_bank = getattr(user, 'max_hqb_bank', None) is not None
        if not has_bank:
            user2 = getMaxhqbBank(user)
            return user2 or user
        return user
    except Exception:
        return user

def _user_to_dict(user):
    return {
        'account': getattr(user, 'account', None),
        'password': getattr(user, 'password', None),
        'c_token': getattr(user, 'c_token', None),
        'u_token': getattr(user, 'u_token', None),
        'customer_no': getattr(user, 'customer_no', None),
        'customer_name': getattr(user, 'customer_name', None),
        'index': getattr(user, 'index', None),
        'passport_id': getattr(user, 'passport_id', None),
        'passport_uid': getattr(user, 'passport_uid', None),
        'passport_ctoken': getattr(user, 'passport_ctoken', None),
        'passport_utoken': getattr(user, 'passport_utoken', None),
        'ts': int(time.time()),
    }

def _save_file_cache(user):
    try:
        data = _user_to_dict(user)
        _FILE_CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False))
    except Exception:
        pass

def _load_file_cache(account: str, password: str):
    try:
        if not _FILE_CACHE_PATH.exists():
            return None
        raw = json.loads(_FILE_CACHE_PATH.read_text())
        if raw.get('account') != account or raw.get('password') != password:
            return None
        ts = raw.get('ts', 0)
        if time.time() - ts > _FILE_CACHE_TTL_SEC:
            return None
        from src.domain.user.User import User
        user = User.from_dict(raw)
        return user
    except Exception:
        return None

def invalidate_user_cache(account: str, password: str):
    key = (account, password)
    with _cache_lock:
        _user_cache.pop(key, None)

def get_user_all_info(account: str, password: str):
    cached = _get_cached_user(account, password)
    if cached is not None:
        cached = _ensure_bank(cached)
        _set_user_cache(cached)
        logger.info("令牌来源: 内存缓存", extra={"account": account, "token_source": "cache"})
        return cached
    file_cached = _load_file_cache(account, password)
    if file_cached is not None:
        file_cached = _ensure_bank(file_cached)
        _set_user_cache(file_cached)
        logger.info("令牌来源: 文件缓存", extra={"account": account, "token_source": "file_cache"})
        return file_cached
    # 若未提供有效密码且为默认账号，使用默认用户密码
    if not password and getattr(DEFAULT_USER, 'account', None) == account:
        password = getattr(DEFAULT_USER, 'password', '')
    store = UserTokenStore()
    db_user = store.get(account)
    if db_user is not None:
        # 填充密码（避免下游交易接口因密码为空抛错）
        try:
            setattr(db_user, 'password', password)
            if not getattr(db_user, 'paypassword', None):
                setattr(db_user, 'paypassword', password)
        except Exception:
            pass
        db_user = _ensure_bank(db_user)
        _set_user_cache(db_user)
        _save_file_cache(db_user)
        logger.info("令牌来源: 数据库", extra={"account": account, "token_source": "database"})
        return db_user
    user = login(account, password)
    if not user:
        logger.error("登录失败", extra={"account": account})
        fallback = DEFAULT_USER if getattr(DEFAULT_USER, 'account', None) == account else None
        if fallback:
            fallback = _ensure_bank(fallback)
            _set_user_cache(fallback)
            _save_file_cache(fallback)
            try:
                UserTokenStore().upsert(fallback)
            except Exception:
                pass
            logger.info("令牌来源: 默认用户", extra={"account": account, "token_source": "default_user"})
            return fallback
        return None
    user = inference_passport_for_bind(user)
    if not user:
        logger.error("passport推断失败", extra={"account": account})
        return None
    user = getMaxhqbBank(user)
    if user:
        _set_user_cache(user)
        _save_file_cache(user)
        try:
            store.upsert(user)
        except Exception:
            pass
        logger.info("令牌来源: 登录聚合", extra={"account": account, "token_source": "login"})
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
    u2 = _ensure_bank(u2)
    _set_user_cache(u2)
    try:
        UserTokenStore().upsert(u2)
    except Exception:
        pass
    logger.info("令牌来源: 刷新凭证", extra={"account": account, "token_source": "refresh"})
    return u2

def get_user_from_store_or_cache(account: str, password: str):
    cached = _get_cached_user(account, password)
    if cached is not None:
        cached = _ensure_bank(cached)
        _set_user_cache(cached)
        logger.info("令牌来源: 内存缓存(无登录)", extra={"account": account, "token_source": "cache_nologin"})
        return cached
    file_cached = _load_file_cache(account, password)
    if file_cached is not None:
        file_cached = _ensure_bank(file_cached)
        _set_user_cache(file_cached)
        logger.info("令牌来源: 文件缓存(无登录)", extra={"account": account, "token_source": "file_cache_nologin"})
        return file_cached
    try:
        # 若未提供有效密码且为默认账号，使用默认用户密码
        if not password and getattr(DEFAULT_USER, 'account', None) == account:
            password = getattr(DEFAULT_USER, 'password', '')
        store = UserTokenStore()
        db_user = store.get(account)
        if db_user is not None:
            # 填充密码（避免下游交易接口因密码为空抛错）
            try:
                setattr(db_user, 'password', password)
                if not getattr(db_user, 'paypassword', None):
                    setattr(db_user, 'paypassword', password)
            except Exception:
                pass
            db_user = _ensure_bank(db_user)
            _set_user_cache(db_user)
            _save_file_cache(db_user)
            logger.info("令牌来源: 数据库(无登录)", extra={"account": account, "token_source": "database_nologin"})
            return db_user
    except Exception:
        pass
    logger.info("令牌来源: 默认用户(无登录)", extra={"account": account, "token_source": "default_user_nologin"})
    return DEFAULT_USER
