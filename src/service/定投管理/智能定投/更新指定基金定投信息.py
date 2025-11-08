import os
import sys
import json
import logging
from typing import List, Dict, Any, Optional

# 动态注入项目根目录，避免 ModuleNotFoundError: No module named 'src'
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.domain.user.User import User
from src.common.constant import DEFAULT_USER
# 模块导入片段
from src.API.定投计划管理.SmartPlan import (
    getFundPlanList,
    getPlanDetailPro,
    updatePlanStatus,
    updateRation,  # 新增：导入金额/止盈更新接口
)
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail

logger = logging.getLogger("更新指定基金定投信息")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_ch)


def _profit_rate_of(rp) -> Optional[str]:
    """优先使用 rationProfitRate，其次 totalProfitRate。"""
    return rp.rationProfitRate or rp.totalProfitRate

def _period_text(period_type: int, period_value: Optional[int]) -> str:
    # 统一展示周期信息
    if period_type == 3:
        return f"每月{str(period_value).rjust(2)}号" if period_value else "每月"
    elif period_type == 2:
        return f"每周{period_value}" if period_value else "每周"
    elif period_type == 4:
        return "每日"
    return f"周期{period_type}(值={period_value})"


def collect_plan_info_for_fund(user: User, fund_code: str, period_type_filter: Optional[int] = 3) -> List[Dict[str, Any]]:
    """
    拉取并汇总指定基金的定投计划信息。
    - period_type_filter: 周期过滤（默认3=月定投）；None 表示不过滤（所有周期）
    - 返回按周期值（periodValue）升序的计划信息列表
    """
    plans = getFundPlanList(fund_code, user)
    if not plans:
        logger.info(f"基金 {fund_code} 没有任何定投计划")
        return []

    results: List[Dict[str, Any]] = []
    for idx, plan in enumerate(plans, start=1):
        try:
            detail_resp = getPlanDetailPro(plan.planId, user)
        except Exception as e:
            logger.warning(f"[{idx}/{len(plans)}] 计划 {plan.planId} 获取详情异常: {e}")
            continue

        if not getattr(detail_resp, "Success", False) or not getattr(detail_resp, "Data", None):
            logger.warning(f"[{idx}/{len(plans)}] 计划 {plan.planId} 获取详情失败: {getattr(detail_resp, 'FirstError', None)}")
            continue

        detail: FundPlanDetail = detail_resp.Data
        rp = detail.rationPlan
        # 周期过滤：默认仅保留 periodType=3（月定投）；None 表示不过滤
        if period_type_filter is not None and rp.periodType != period_type_filter:
            continue

        info = {
            "planId": rp.planId,
            "fundCode": rp.fundCode,
            "fundName": rp.fundName,
            "amount": rp.amount,
            "periodType": rp.periodType,
            "periodValue": rp.periodValue,
            "subAccountName": rp.subAccountName,
            "subAccountNo": rp.subAccountNo,
            "bankAccountNo": rp.bankAccountNo,
            "payType": rp.payType,
            "buyStrategy": rp.buyStrategy,
            "redeemStrategy": rp.redeemStrategy,
            "planAssets": rp.planAssets,
            "profitRate": _profit_rate_of(rp),
            "planState": rp.planState,
            "planExtendStatus": rp.planExtendStatus,
            "planBusinessState": rp.planBusinessState,
            "pauseType": rp.pauseType,
            "currentDay": rp.currentDay,
        }
        results.append(info)

    # 按周期值升序（若无则置0）
    results.sort(key=lambda x: (x.get("periodValue") or 0, x.get("planId")))
    label = "定投计划" if period_type_filter is None else f"{_period_text(period_type_filter, None)}定投计划"
    logger.info(f"基金 {fund_code} 已识别到 {len(results)} 个{label}")
    for r in results:
        label_r = _period_text(r["periodType"], r["periodValue"])
        logger.info(
            f"  {label_r} -> 计划ID: {r['planId']}, 金额: {r['amount']:.2f}, 子账户: {r['subAccountName']}, "
            f"资产: {r['planAssets']}, 盈亏率: {r['profitRate']}"
        )
    return results


def update_smart_investment_info(
    user: User,
    fund_code: str,
    buy_strategy_switch: Optional[bool] = None,
    amount: Optional[Any] = None,
    profit_percent: Optional[Any] = None,
    output_path: Optional[str] = None,
    period_type_filter: Optional[int] = 3,  # 默认月定投；None 更新所有周期
) -> Dict[str, Any]:
    """
    刷新并更新指定基金的定投信息（支持任意周期，通过 period_type_filter 过滤）。
    """
    plans = collect_plan_info_for_fund(user, fund_code, period_type_filter)

    update_results: Optional[List[Dict[str, Any]]] = None
    if buy_strategy_switch is not None and plans:
        update_results = []
        label = "定投买入状态"
        logger.info(
            f"批量更新基金 {fund_code} 的{label}为: {'恢复买入' if buy_strategy_switch else '暂停买入'}（周期过滤={period_type_filter if period_type_filter is not None else '所有'}）"
        )
        for r in plans:
            plan_id = r["planId"]
            try:
                resp = updatePlanStatus(user, plan_id, buy_strategy_switch)
                ok = getattr(resp, "Success", False)

                # 二次查询校验“是否真正生效”
                post_verified = False
                new_state = None
                if ok:
                    try:
                        verify = getPlanDetailPro(plan_id, user)
                        if getattr(verify, "Success", False) and getattr(verify, "Data", None):
                            new_state = str(verify.Data.rationPlan.buyStrategy)
                            expected = "1" if buy_strategy_switch else "0"
                            post_verified = (new_state == expected)
                    except Exception as _ve:
                        logger.warning(f"[校验] 计划 {plan_id} 二次查询异常: {_ve}")

                update_results.append(
                    {
                        "planId": plan_id,
                        "periodValue": r["periodValue"],
                        "periodType": r["periodType"],
                        "subAccountName": r["subAccountName"],
                        "success": ok,
                        "verified": post_verified,
                        "newBuyStrategy": new_state,
                        "error": getattr(resp, "FirstError", None),
                        "action": "update_buy_strategy"
                    }
                )
                label_r = _period_text(r["periodType"], r["periodValue"])
                if ok and post_verified:
                    logger.info(f"✓ {plan_id} {label_r} 状态更新并已验证生效")
                elif ok and not post_verified:
                    logger.warning(f"⚠ {plan_id} {label_r} 更新返回成功，但校验未生效（newBuyStrategy={new_state}）")
                else:
                    logger.warning(f"✗ {plan_id} {label_r} 更新失败: {getattr(resp, 'FirstError', None)}")
            except Exception as e:
                label_r = _period_text(r["periodType"], r["periodValue"])
                logger.error(f"✗ {plan_id} {label_r} 更新异常: {e}")
                update_results.append(
                    {
                        "planId": plan_id,
                        "periodValue": r["periodValue"],
                        "periodType": r["periodType"],
                        "subAccountName": r["subAccountName"],
                        "success": False,
                        "verified": False,
                        "newBuyStrategy": None,
                        "error": str(e),
                        "action": "update_buy_strategy"
                    }
                )

    # 删除旧的“已忽略参数”提示，改为更明确的非执行说明
    # 以上块保持：买入开关批量更新 + 二次校验

    # ---------------- 批量更新金额与止盈（targetRate）并校验 ----------------
    def _normalize_target_rate(v: Optional[Any]) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        if s.endswith("%"):
            return s
        try:
            num = float(s)
            return f"{num:g}%"
        except Exception:
            return None

    def _parse_amount(v: Optional[Any]) -> Optional[float]:
        if v is None:
            return None
        try:
            cleaned = str(v).replace("元", "").replace(",", "").strip()
            if cleaned == "":
                return None
            return float(cleaned)
        except Exception:
            return None

    modify_results: Optional[List[Dict[str, Any]]] = None
    need_modify = (amount is not None and str(amount).strip() != "") or (profit_percent is not None and str(profit_percent).strip() != "")
    if need_modify and plans:
        modify_results = []
        logger.info(f"批量更新基金 {fund_code} 的参数: amount={amount}, targetRate={profit_percent}（周期过滤={period_type_filter if period_type_filter is not None else '所有'}）")
        expected_amount = _parse_amount(amount)
        expected_target = _normalize_target_rate(profit_percent)

        for r in plans:
            plan_id = r["planId"]
            try:
                resp = updateRation(
                    user,
                    plan_id,
                    amount=amount if (amount is not None and str(amount).strip() != "") else None,
                    targetRate=profit_percent if (profit_percent is not None and str(profit_percent).strip() != "") else None,
                )
                ok = getattr(resp, "Success", False)

                # 二次查询校验金额/止盈
                verified = False
                new_amount = None
                new_target_rate = None
                if ok:
                    try:
                        verify = getPlanDetailPro(plan_id, user)
                        if getattr(verify, "Success", False) and getattr(verify, "Data", None):
                            vrp = verify.Data.rationPlan
                            new_amount = vrp.amount
                            new_target_rate = vrp.targetRate
                            cond_amount = True if expected_amount is None else (abs((new_amount or 0.0) - expected_amount) < 1e-6)
                            cond_target = True if expected_target is None else (str(new_target_rate or "").strip() == expected_target)
                            verified = cond_amount and cond_target
                    except Exception as _ve:
                        logger.warning(f"[参数校验] 计划 {plan_id} 二次查询异常: {_ve}")

                modify_results.append(
                    {
                        "planId": plan_id,
                        "periodValue": r["periodValue"],
                        "periodType": r["periodType"],
                        "subAccountName": r["subAccountName"],
                        "success": ok,
                        "verified": verified,
                        "newAmount": new_amount,
                        "newTargetRate": new_target_rate,
                        "error": getattr(resp, "FirstError", None),
                        "action": "update_ration",
                    }
                )
                label_r = _period_text(r["periodType"], r["periodValue"])
                if ok and verified:
                    logger.info(f"✓ {plan_id} {label_r} 金额/止盈更新并已验证生效")
                elif ok and not verified:
                    logger.warning(f"⚠ {plan_id} {label_r} 更新返回成功，但校验未生效（newAmount={new_amount}, newTargetRate={new_target_rate}）")
                else:
                    logger.warning(f"✗ {plan_id} {label_r} 更新失败: {getattr(resp, 'FirstError', None)}")
            except Exception as e:
                label_r = _period_text(r["periodType"], r["periodValue"])
                logger.error(f"✗ {plan_id} {label_r} 更新异常: {e}")
                modify_results.append(
                    {
                        "planId": plan_id,
                        "periodValue": r["periodValue"],
                        "periodType": r["periodType"],
                        "subAccountName": r["subAccountName"],
                        "success": False,
                        "verified": False,
                        "newAmount": None,
                        "newTargetRate": None,
                        "error": str(e),
                        "action": "update_ration",
                    }
                )

    # ---------------- 结果汇总 ----------------
    result = {
        "fundCode": fund_code,
        "count": len(plans),
        "plans": plans,
        "updateResults": update_results,
        "modifyResults": modify_results,
        "periodTypeFilter": period_type_filter,  # 返回中透出本次周期过滤
    }
    return result


if __name__ == "__main__":
    info = update_smart_investment_info(
        user=DEFAULT_USER,
        fund_code="001595",
        buy_strategy_switch=False,
        amount="10000.0",            # 更新金额为 10000
        profit_percent="10.0%",      # 更新目标止盈为 10%
        period_type_filter=3         # 仅更新月定投；传 None 则所有周期
    )
    logger.info(f"完成，共 {info['count']} 个匹配的定投计划（周期过滤={info.get('periodTypeFilter')}）")

    # 买入开关更新汇总
    update_results = info.get("updateResults") or []
    if update_results:
        ok = sum(1 for r in update_results if r.get("success"))
        fail = len(update_results) - ok
        print(f"[买入开关更新] 成功: {ok} 失败: {fail}")
        for r in update_results:
            status = "成功" if r.get("success") else f"失败({r.get('error')})"
            verify = "已生效" if r.get("verified") else "未生效"
            label_r = _period_text(r.get("periodType"), r.get("periodValue"))
            print(f"- 计划 {r.get('planId')} {label_r} {r.get('action')} -> {status} / 校验:{verify}, 新开关={r.get('newBuyStrategy')}")
    else:
        print("未执行买入开关更新（buy_strategy_switch 未指定）")

    # 金额/止盈更新汇总
    modify_results = info.get("modifyResults") or []
    if modify_results:
        ok = sum(1 for r in modify_results if r.get("success"))
        fail = len(modify_results) - ok
        print(f"[金额/止盈更新] 成功: {ok} 失败: {fail}")
        for r in modify_results:
            status = "成功" if r.get("success") else f"失败({r.get('error')})"
            verify = "已生效" if r.get("verified") else "未生效"
            label_r = _period_text(r.get("periodType"), r.get("periodValue"))
            print(f"- 计划 {r.get('planId')} {label_r} {r.get('action')} -> {status} / 校验:{verify}, 新金额={r.get('newAmount')}, 新止盈={r.get('newTargetRate')}")
    else:
        print("未执行金额/止盈更新（amount/profit_percent 未指定或周期内无匹配计划）")
    # 明确提示忽略的参数
    ignored = info.get("ignoredParams")
    if ignored:
        print(f"已忽略参数: {ignored}（不删除不重建，不做金额/止盈修改）")