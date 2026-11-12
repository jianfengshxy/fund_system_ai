from __future__ import annotations

import importlib
from types import SimpleNamespace


service_module = importlib.import_module("src.service.大数据.增加智投平台基金到自选组合")


def _build_theme(*, sec_code: str, sec_name: str, isshow: bool = True, corr_1y: float = 0.0):
    return SimpleNamespace(
        sec_code=sec_code,
        sec_name=sec_name,
        isshow=isshow,
        corr_1y=corr_1y,
    )


def test_build_candidate_group_keys_only_uses_themes_above_70():
    candidate = {
        "index_code": "IDX001",
        "themes": [
            {"theme_code": "BK000001", "theme_name": "低匹配主题", "match_score": 70.0},
            {"theme_code": "BK000002", "theme_name": "高匹配主题", "match_score": 70.01},
            {"theme_code": "BK000003", "theme_name": "无分数主题", "match_score": None},
        ],
    }

    group_keys = service_module._build_candidate_group_keys(candidate)

    assert group_keys == ["theme:BK000002"]


def test_resolve_candidate_themes_only_uses_related_theme_scores_for_dedup():
    snapshot = {
        "sec_code": "BK000003",
        "sec_name": "直连主题",
    }
    fund_info = SimpleNamespace(
        theme_infos=[
            _build_theme(sec_code="BK000001", sec_name="弱相关主题", isshow=True),
            _build_theme(sec_code="BK000002", sec_name="强相关主题", isshow=False),
        ],
        relate_themes=[
            _build_theme(sec_code="BK000001", sec_name="弱相关主题", corr_1y=65.0),
            _build_theme(sec_code="BK000002", sec_name="强相关主题", corr_1y=82.5),
        ],
    )

    themes = service_module._resolve_candidate_themes(snapshot, fund_info)

    assert themes == [
        {"theme_code": "BK000001", "theme_name": "弱相关主题", "match_score": 65.0},
        {"theme_code": "BK000002", "theme_name": "强相关主题", "match_score": 82.5},
        {"theme_code": "BK000003", "theme_name": "直连主题", "match_score": None},
    ]


def test_dedup_candidates_by_theme_allows_overlap_when_match_score_not_above_70():
    candidates = [
        {
            "fund_code": "FUND_A",
            "fund_name": "基金A",
            "index_code": "IDX_A",
            "latest_heat_score": 80.0,
            "latest_main_net_inflow": 100_000_000.0,
            "themes": [{"theme_code": "BK000111", "theme_name": "低匹配主题", "match_score": 68.0}],
        },
        {
            "fund_code": "FUND_B",
            "fund_name": "基金B",
            "index_code": "IDX_B",
            "latest_heat_score": 70.0,
            "latest_main_net_inflow": 90_000_000.0,
            "themes": [{"theme_code": "BK000111", "theme_name": "低匹配主题", "match_score": 69.5}],
        },
    ]

    result = service_module._dedup_candidates_by_theme(candidates)

    assert [row["fund_code"] for row in result] == ["FUND_A", "FUND_B"]


def test_dedup_candidates_by_theme_blocks_overlap_when_match_score_above_70():
    candidates = [
        {
            "fund_code": "FUND_A",
            "fund_name": "基金A",
            "index_code": "IDX_A",
            "latest_heat_score": 88.0,
            "latest_main_net_inflow": 120_000_000.0,
            "themes": [{"theme_code": "BK000222", "theme_name": "高匹配主题", "match_score": 85.0}],
        },
        {
            "fund_code": "FUND_B",
            "fund_name": "基金B",
            "index_code": "IDX_B",
            "latest_heat_score": 75.0,
            "latest_main_net_inflow": 110_000_000.0,
            "themes": [{"theme_code": "BK000222", "theme_name": "高匹配主题", "match_score": 83.0}],
        },
    ]

    result = service_module._dedup_candidates_by_theme(candidates)

    assert [row["fund_code"] for row in result] == ["FUND_A"]
