from typing import Optional, Tuple


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def get_primary_theme(fund_info) -> Optional[Tuple[str, str]]:
    """
    提取基金主主题：
    1. 优先 theme_infos 中 isshow=True 的首个主题
    2. 否则退回 relate_themes 中 corr_1y 最高的主题
    """
    if not fund_info:
        return None

    theme_infos = getattr(fund_info, "theme_infos", None) or []
    show_themes = [theme for theme in theme_infos if getattr(theme, "isshow", False)]
    if show_themes:
        theme = show_themes[0]
        sec_code = str(getattr(theme, "sec_code", "") or "").strip()
        sec_name = str(getattr(theme, "sec_name", "") or "").strip()
        if sec_code or sec_name:
            return sec_code, sec_name

    relate_themes = getattr(fund_info, "relate_themes", None) or []
    if relate_themes:
        theme = max(relate_themes, key=lambda item: _safe_float(getattr(item, "corr_1y", 0.0), 0.0))
        sec_code = str(getattr(theme, "sec_code", "") or "").strip()
        sec_name = str(getattr(theme, "sec_name", "") or "").strip()
        if sec_code or sec_name:
            return sec_code, sec_name

    return None


def format_theme_label(fund_info) -> str:
    theme = get_primary_theme(fund_info)
    if not theme:
        return "未知主题"

    sec_code, sec_name = theme
    if sec_name and sec_code:
        return f"{sec_name}({sec_code})"
    return sec_name or sec_code or "未知主题"


def get_theme_group_key_and_label(fund_info) -> Tuple[Optional[str], str]:
    """
    所有基金统一按主题优先分组：
    - 只要能提取到主题，就按主题去重
    - 拿不到主题时，再退回 index_code
    """
    if not fund_info:
        return None, "未知分组"

    theme = get_primary_theme(fund_info)
    if theme:
        sec_code, sec_name = theme
        if sec_code:
            return f"theme_code:{sec_code}", f"同主题({sec_name or sec_code})"
        if sec_name:
            return f"theme_name:{sec_name}", f"同主题({sec_name})"

    index_code = str(getattr(fund_info, "index_code", "") or "").strip()
    if index_code:
        return f"index:{index_code}", f"同指数({index_code})"

    return None, "未知分组"
