import os
import sys
import logging
import yaml
import json
from typing import Dict
from pathlib import Path

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[3]
    project_root_str = str(project_root)
    if project_root_str not in sys.path:
        sys.path.insert(0, project_root_str)

from src.domain.user.User import User
from src.API.定投计划管理.SmartPlan import getFundPlanList, getPlanDetailPro, getFundRations
from src.service.交易管理.赎回基金 import sell_0_fee_shares, sell_low_fee_shares
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.交易管理.trade import get_bank_shares
from src.common.constant import DEFAULT_USER
from src.service.公共服务.estimated_profit_service import calc_estimated_change, calc_estimated_profit_rate

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("FixedRatioRedeem")


def get_plans_for_fund(user: User, fund_code: str):
    """优先查询全部定投类型，再按基金代码过滤，避免遗漏组合定投计划。"""
    try:
        response = getFundRations(user, page_index=1, page_size=1000, planTypes=[1, 2])
        if response.Success and response.Data:
            matched_plans = [
                plan for plan in response.Data
                if str(getattr(plan, 'fundCode', '')).strip() == str(fund_code).strip()
            ]
            if matched_plans:
                plan_type_summary = {}
                for plan in matched_plans:
                    plan_type = str(getattr(plan, 'planType', '') or 'unknown')
                    plan_type_summary[plan_type] = plan_type_summary.get(plan_type, 0) + 1
                logger.info(
                    f"基金 {fund_code} 在全量定投列表中找到 {len(matched_plans)} 个计划，planType 分布: {plan_type_summary}"
                )
                return matched_plans
            logger.info(f"基金 {fund_code} 未在全量定投列表中命中任何计划")
    except Exception as e:
        logger.warning(f"查询基金 {fund_code} 全量定投计划失败，将回退到旧接口: {e}")

    # 兼容旧逻辑：仅查询目标止盈定投
    fallback_plans = getFundPlanList(fund_code, user) or []
    logger.info(f"基金 {fund_code} 在旧接口(仅目标止盈定投)中找到 {len(fallback_plans)} 个计划")
    return fallback_plans


def enrich_plan_from_detail(plan, user: User):
    """用详情接口补齐子账户和周期信息，避免列表接口字段缺失。"""
    try:
        detail_resp = getPlanDetailPro(plan.planId, user)
        if detail_resp.Success and detail_resp.Data and detail_resp.Data.rationPlan:
            ration_plan = detail_resp.Data.rationPlan
            if not getattr(plan, 'subAccountNo', ''):
                plan.subAccountNo = getattr(ration_plan, 'subAccountNo', '') or getattr(plan, 'subAccountNo', '')
            if not getattr(plan, 'subAccountName', ''):
                plan.subAccountName = getattr(ration_plan, 'subAccountName', '') or getattr(plan, 'subAccountName', '')
            if not getattr(plan, 'periodType', 0):
                plan.periodType = getattr(ration_plan, 'periodType', 0) or getattr(plan, 'periodType', 0)
            if not getattr(plan, 'periodValue', 0):
                plan.periodValue = getattr(ration_plan, 'periodValue', 0) or getattr(plan, 'periodValue', 0)
            return plan, ration_plan
        logger.warning(f"无法获取计划 {plan.planId} 的详情，跳过")
    except Exception as e:
        logger.error(f"获取计划 {plan.planId} 详情失败: {e}")
    return plan, None

def load_config(yaml_path: str) -> Dict:
    """加载 YAML 配置"""
    if not os.path.exists(yaml_path):
        logger.error(f"配置文件未找到: {yaml_path}")
        return {}
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        try:
            config = yaml.safe_load(f)
            vars_config = config.get('vars', {})
            
            # 优先尝试读取 fixed_ratio_redeem_payload (JSON string)
            payload_str = vars_config.get('fixed_ratio_redeem_payload')
            if payload_str:
                try:
                    return json.loads(payload_str)
                except json.JSONDecodeError as e:
                    logger.error(f"解析 fixed_ratio_redeem_payload JSON 失败: {e}")
            
            # 兼容旧配置 fixed_ratio_redeem_config (Dict)
            return vars_config.get('fixed_ratio_redeem_config', {})
            
        except yaml.YAMLError as e:
            logger.error(f"解析 YAML 失败: {e}")
            return {}

def process_fixed_ratio_redeem(user: User, config: Dict):
    """处理固定比率止盈"""
    fund_list = config.get('fundcodelist', [])
    if not fund_list:
        logger.info("未配置基金列表")
        return

    logger.info(f"开始执行固定比率止盈检查，用户: {user.customer_name}，共 {len(fund_list)} 个基金")

    for fund_item in fund_list:
        fund_code = fund_item.get('fundcode')
        stop_rate_str = fund_item.get('stoprate')
        target_period_type = fund_item.get('periodtype')
        if target_period_type is None:
            target_period_type = fund_item.get('periodType')
        target_period_type = str(target_period_type).strip() if target_period_type is not None else ""
        
        if not fund_code or not stop_rate_str:
            logger.warning(f"配置项缺失: {fund_item}")
            continue
            
        try:
            stop_rate = float(stop_rate_str)
        except ValueError:
            logger.error(f"止盈率格式错误: {stop_rate_str}")
            continue

        logger.info(f"检查基金 {fund_code}，目标止盈率: {stop_rate}%")
        
        try:
            # 获取该基金的所有定投计划（覆盖目标止盈定投 + 组合定投）
            all_plans = get_plans_for_fund(user, fund_code)
            if not all_plans:
                logger.info(f"基金 {fund_code} 没有找到定投计划，请重点检查账号是否正确、计划是否处于有效状态、以及计划类型是否为普通组合定投")
                continue

            # 未传 periodtype 时，默认处理该基金全部周期的定投计划
            if not target_period_type:
                plans = []
                for plan in all_plans:
                    enriched_plan, _ = enrich_plan_from_detail(plan, user)
                    if not getattr(enriched_plan, 'subAccountNo', ''):
                        logger.warning(f"计划 {plan.planId} 缺少 subAccountNo，无法继续处理，跳过")
                        continue
                    plans.append(enriched_plan)
                logger.info(f"基金 {fund_code} 未指定 periodtype，默认处理全部 {len(plans)} 个定投计划")
            else:
                plans = []
                for plan in all_plans:
                    # 查询定投计划详情以获取准确的周期类型，并补齐 subAccountNo
                    # 列表接口返回的 periodType 往往为 0，且 getFundRations 不返回 subAccountNo
                    enriched_plan, ration_plan = enrich_plan_from_detail(plan, user)
                    if ration_plan and str(ration_plan.periodType) == target_period_type:
                        if not getattr(enriched_plan, 'subAccountNo', ''):
                            logger.warning(f"计划 {plan.planId} 匹配 periodtype={target_period_type} 但缺少 subAccountNo，跳过")
                            continue
                        plans.append(enriched_plan)

                logger.info(
                    f"基金 {fund_code} 共找到 {len(all_plans)} 个计划，按 periodtype={target_period_type} 过滤后剩余 {len(plans)} 个"
                )
            
            if not plans:
                continue
                
            # 遍历每个计划进行检查
            for plan in plans:
                sub_account_no = plan.subAccountNo
                sub_account_name = plan.subAccountName
                
                # 获取基金基本信息
                fund_info = get_all_fund_info(user, fund_code)
                fund_name = fund_info.fund_name

                display_name = sub_account_name if sub_account_name else fund_name
                logger.info(f"检查定投计划: {display_name} ({sub_account_no})")
                
                # 获取资产详情
                asset_detail = get_fund_asset_detail(user, sub_account_no, fund_code)
                if not asset_detail:
                    # logger.info(f"组合 {sub_account_name} 的基金 {fund_name}({fund_code}) 资产为空，跳过")
                    continue
                
                # 获取可用份额
                shares = get_bank_shares(user, sub_account_no, fund_code)
                if not shares:
                    logger.info(f"组合 {sub_account_name} 的基金 {fund_name}({fund_code}) 可用份额为空，跳过")
                    continue

                # 计算预估收益率
                current_profit_rate = asset_detail.constant_profit_rate if asset_detail.constant_profit_rate is not None else 0.0
                estimated_change, label_est = calc_estimated_change(fund_info)
                estimated_profit_rate = current_profit_rate + estimated_change
                
                logger.info(f"基金 {fund_name}({fund_code}) - 当前收益率: {current_profit_rate}%, 估值增长: {estimated_change}%, 预估总收益: {estimated_profit_rate:.2f}% (目标: {stop_rate}%)（{label_est}）")
                
                # 判断是否满足止盈条件
                if estimated_profit_rate >= stop_rate:
                    if fund_info.fund_type == "000":
                        logger.info(f"满足止盈条件（指数基金）！开始卖出低费率份额...")
                        result = sell_low_fee_shares(user, sub_account_no, fund_code, shares)
                    else:
                        logger.info(f"满足止盈条件！开始卖出 0 费率份额...")
                        result = sell_0_fee_shares(user, sub_account_no, fund_code, shares)

                    if result:
                        logger.info(f"止盈操作提交成功: {result}")
                    else:
                        logger.warning(f"止盈操作未产生交易记录 (可能无符合条件的份额)")
                else:
                    logger.info(f"未达到止盈点，继续持有")

        except Exception as e:
            logger.error(f"处理基金 {fund_code} 时发生错误: {e}", exc_info=True)

if __name__ == "__main__":
    yaml_file = os.path.join(root_dir, 's.yaml')
    config = load_config(yaml_file)
    
    if config:
        # 这里使用 DEFAULT_USER，实际场景可能需要根据 config 中的 account 创建 user
        # 考虑到 DEFAULT_USER 已经在 global 导入并初始化，直接使用
        if config.get('account') == DEFAULT_USER.account:
             process_fixed_ratio_redeem(DEFAULT_USER, config)
        else:
            logger.warning(f"配置用户 {config.get('account')} 与默认用户 {DEFAULT_USER.account} 不匹配")
    else:
        logger.error("无法加载配置或配置为空")
