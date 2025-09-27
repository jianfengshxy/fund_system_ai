#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import time
from typing import Dict, Any, List, Tuple
import argparse

# 项目根路径加入 sys.path，方便导入 src 包
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

import yaml  # PyYAML 在 requirements.txt 中已存在

# 业务与领域导入
from src.domain.user.User import User
from src.service.用户管理.用户信息 import get_user_all_info
from src.API.定投计划管理.SmartPlan import getFundRations, getPlanDetailPro, operateRation
from src.bussiness.组合定投.指数型组合定投管理 import dissolve_plan_by_group_for_index_funds
from src.bussiness.组合定投.主动型组合定投管理 import dissolve_plan_by_group


def load_s_yaml(s_yaml_path: str) -> Dict[str, Any]:
    if not os.path.exists(s_yaml_path):
        raise FileNotFoundError(f"s.yaml not found at: {s_yaml_path}")
    with open(s_yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def parse_triggers_for_user_groups(s_doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    遍历 resources.*.props.triggers[*].triggerConfig.payload，抽取 user/组合/预算 信息
    返回示例项：
    {
        "account": "13918199137",
        "password": "sWX15706",
        "sub_account_name": "飞龙在天",
        "total_budget": 1000000.0,
        "fund_type": "non_index"  # 可选
    }
    """
    results: List[Dict[str, Any]] = []
    resources = (s_doc or {}).get("resources", {})
    for res_name, res_body in resources.items():
        props = (res_body or {}).get("props", {})
        triggers = props.get("triggers", []) or []
        for trig in triggers:
            trig_cfg = (trig or {}).get("triggerConfig", {})
            payload_raw = trig_cfg.get("payload")
            if not payload_raw:
                continue
            try:
                # payload 在 s.yaml 中为 JSON 字符串
                payload = json.loads(payload_raw)
            except Exception:
                # 某些场景可能出现非严格 JSON，尝试放宽处理
                try:
                    payload = json.loads(str(payload_raw).replace("'", '"'))
                except Exception:
                    # 无法解析则跳过
                    continue

            account = payload.get("account")
            password = payload.get("password")
            sub_account_name = payload.get("sub_account_name")
            total_budget = payload.get("total_budget")
            fund_type = payload.get("fund_type")  # 可能不存在

            if not account or not password or not sub_account_name:
                # 必需字段缺失，跳过
                continue

            results.append(
                {
                    "resource": res_name,
                    "account": account,
                    "password": password,
                    "sub_account_name": sub_account_name,
                    "total_budget": total_budget,
                    "fund_type": fund_type,
                }
            )
    return results


def deduplicate_user_groups(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    按 (account, sub_account_name) 去重，采用最后一次出现的配置（密码/预算）。
    """
    merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for e in entries:
        key = (e["account"], e["sub_account_name"])
        merged[key] = e  # 最后一次覆盖前面的
    return list(merged.values())


def is_index_portfolio(sub_account_name: str, fund_type: str | None) -> bool:
    """
    判定是否为指数型组合：
    - 优先使用 fund_type == 'index'
    - 其次基于 sub_account_name 包含“指数”
    """
    if fund_type and str(fund_type).lower() == "index":
        return True
    if "指数" in (sub_account_name or ""):
        return True
    return False


def is_index_group(entry: Dict[str, Any], sub_account_name: str) -> bool:
    """
    判断该组合是否为指数型：
    1) 优先依据 entry['fund_type']，若包含“指数”或等于 index/index_fund 则认为是指数型
    2) 回退：看 sub_account_name 是否包含“指数”或英文 index
    """
    ft = entry.get("fund_type")
    if isinstance(ft, str) and ft.strip():
        ft_raw = ft.strip()
        ft_norm = ft_raw.lower()
        if ("指数" in ft_raw) or (ft_norm in ("index", "index_fund", "index-fund")):
            return True
        return False

    name = (sub_account_name or "")
    name_norm = name.lower()
    return ("指数" in name) or ("index" in name_norm)


def dissolve_for_one(entry: Dict[str, Any], delay_seconds: float) -> bool:
    account = entry["account"]
    password = entry["password"]
    sub_account_name = entry["sub_account_name"]

    # 与 index.py 一致：服务层获取完整用户信息并判空
    user = get_user_all_info(account, password)
    if not user:
        print(f"获取用户 {account} 信息失败，跳过该组合: {sub_account_name}")
        return False

    # 预算：payload.total_budget -> user.budget -> 默认值（仅用于日志）
    total_budget = entry.get("total_budget")
    if total_budget is None:
        total_budget = getattr(user, "budget", None)
    if total_budget is None:
        total_budget = 100000.0

    print(f"开始解散定投：account={account} sub_account_name={sub_account_name} budget={total_budget}")

    # 查询该子账户下的所有组合定投计划
    plans = list_portfolio_plans_by_sub_account(user, sub_account_name)
    if not plans:
        print(f"未找到子账户 '{sub_account_name}' 的组合定投计划，跳过。")
        return True

    success_cnt = 0
    fail_cnt = 0

    for p in plans:
        plan_id = p["plan_id"]
        fund_code = p.get("fund_code", "")
        fund_name = p.get("fund_name", "")
        try:
            print(f"  🗑️ 解散计划: {fund_name}({fund_code}) - planId={plan_id}")
            resp = operateRation(user=user, plan_id=plan_id, operation="2")
            ok = bool(getattr(resp, "Success", False))
            if ok:
                print(f"    ✅ 成功解散: {fund_name}({fund_code})")
                success_cnt += 1
            else:
                print(f"    ❌ 失败: {fund_name}({fund_code}) "
                      f"error={getattr(resp, 'FirstError', None) or getattr(resp, 'DebugError', None)}")
                fail_cnt += 1
        except Exception as e:
            print(f"    ❌ 调用解散API异常: {e}")
            fail_cnt += 1
        finally:
            # 每次调用之间加入延时，避免限频
            time.sleep(delay_seconds)

    print(f"组合 '{sub_account_name}' 解散完成：成功 {success_cnt}，失败 {fail_cnt}，共 {len(plans)}")
    return fail_cnt == 0
    # 指数/主动型分流
    if is_index_group(entry, sub_account_name):
        ok = dissolve_plan_by_group_for_index_funds(user, sub_account_name, float(total_budget))
    else:
        ok = dissolve_plan_by_group(user, sub_account_name, float(total_budget))

    return bool(ok)


def main():
    s_yaml_path = os.path.join(PROJECT_ROOT, "s.yaml")

    parser = argparse.ArgumentParser(description="从 s.yaml 读取用户与组合并解散定投")
    parser.add_argument("--delay-seconds", type=float, default=5.0, help="每次调用之间的延时秒数，默认 5 秒")
    args = parser.parse_args()

    print(f"读取配置: {s_yaml_path}")
    s_doc = load_s_yaml(s_yaml_path)

    all_entries = parse_triggers_for_user_groups(s_doc)
    if not all_entries:
        print("未在 s.yaml 的 triggers 中解析到任何用户与组合的 payload，退出。")
        return

    # 去重
    unique_entries = deduplicate_user_groups(all_entries)
    print(f"共解析到 {len(all_entries)} 条触发配置，去重后 {len(unique_entries)} 条（按 account+sub_account_name）")

    success = 0
    failure = 0
    for i, entry in enumerate(unique_entries, start=1):
        print(f"\n[{i}/{len(unique_entries)}] 开始处理: {entry['account']} - {entry['sub_account_name']}")
        ok = dissolve_for_one(entry, args.delay_seconds)
        if ok:
            success += 1
        else:
            failure += 1
        # 防抖：避免过快调用（条目与条目之间）
        time.sleep(args.delay_seconds)

    print("\n处理完成")
    print(f"成功: {success}, 失败: {failure}, 合计: {len(unique_entries)}")


def list_portfolio_plans_by_sub_account(user, sub_account_name: str) -> List[Dict[str, Any]]:
    """
    拉取所有组合定投计划(planTypes=[2])，并按子账户名称过滤，返回包含 planId/fundCode/fundName 的列表
    """
    results: List[Dict[str, Any]] = []
    try:
        resp = getFundRations(user, page_index=1, page_size=1000, planTypes=[2])
    except Exception as e:
        print(f"获取组合定投计划失败: {e}")
        return results

    if not getattr(resp, "Success", False) or not getattr(resp, "Data", None):
        return results

    for plan in resp.Data:
        try:
            detail = getPlanDetailPro(plan.planId, user)
            if getattr(detail, "Success", False) and getattr(detail, "Data", None):
                rp = detail.Data.rationPlan
                if getattr(rp, "subAccountName", "") == sub_account_name:
                    results.append({
                        "plan_id": getattr(rp, "planId", plan.planId),
                        "fund_code": getattr(rp, "fundCode", getattr(plan, "fundCode", "")),
                        "fund_name": getattr(rp, "fundName", getattr(plan, "fundName", "")),
                    })
        except Exception as e:
            print(f"获取计划 {getattr(plan, 'planId', '')} 详情失败: {e}")
            continue

    return results


if __name__ == "__main__":
    main()