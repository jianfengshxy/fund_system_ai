# 顶部导入处（新增公共方法引用）
import logging
import os
import sys
from typing import Optional

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
from src.service.基金信息.基金信息 import get_all_fund_info
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.资产管理.get_fund_asset_detail import (
    get_sub_account_asset_by_name,
)
from src.service.交易管理.购买基金 import commit_order
from src.common.constant import DEFAULT_USER
from src.service.公共服务.nav_gate_service import nav5_gate
from src.service.公共服务.risk_control_service import check_hqb_risk_allowed
from src.service.公共服务.fund_theme_group_service import get_theme_group_key_and_label
from src.service.公共服务.index_heat_service import get_latest_realtime_index_heat

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 活期宝风控阈值常量
HQB_THRESHOLD = 10

# 组合仓位占比阈值常量
ASSET_RATIO_THRESHOLD = 80

def increase_funds(user: User, sub_account_name: str, fund_list: Optional[list] = None, total_budget: float = 100000.0) -> bool:
    """自定义组合算法新增：从 payload 传入的 fund_list 获取要交易的基金及其金额。
    对于组合中未持有的基金，直接按 amount 进行购买；已持有基金暂不处理。
    """
    customer_name = user.customer_name
    logger.info(f"开始为用户 {customer_name} 执行新增操作，组合: {sub_account_name}，预算: {total_budget}")

    # 0) 全局风控检查：活期宝占比
    if not check_hqb_risk_allowed(user,threshold=HQB_THRESHOLD):
        logger.info(f"[自定义组合] 全局风控拦截：活期宝占比不足{HQB_THRESHOLD}，退出新增流程")
        return False

    # 0.1) 组合预算风控检查
    if total_budget > 0:
        asset_details = get_sub_account_asset_by_name(user, sub_account_name) or []
        current_holdings = sum(float(getattr(a, 'asset_value', 0) or 0) for a in asset_details)
        
        ratio = (current_holdings / total_budget) * 100
        if ratio > ASSET_RATIO_THRESHOLD:
            logger.info(f"[自定义组合] 预算风控拦截：当前组合资产({current_holdings:.2f})已超过预算({total_budget})的{ASSET_RATIO_THRESHOLD}% (当前{ratio:.2f}%)，退出新增流程")
            return False
        else:
            logger.info(f"[自定义组合] 预算检查通过：当前资产占比 {ratio:.2f}% (阈值 {ASSET_RATIO_THRESHOLD}%)")
    else:
        # 如果没有传预算，则跳过此检查，但为了后续逻辑，我们需要获取 asset_details
        # 注意：下面的逻辑中第 56 行又获取了一次 asset_details，可以优化
        pass

    # 获取组合账号
    sub_account_no = getSubAccountNoByName(user, sub_account_name)
    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return False

    # 校验 payload 的基金列表
    if not fund_list or not isinstance(fund_list, list):
        logger.info(f"未提供 fund_list 或格式不正确，跳过自定义组合新增")
        return False

    fund_info_cache = {}
    index_heat_cache = {}

    def _get_cached_fund_info(fund_code: str):
        if not fund_code:
            return None
        if fund_code not in fund_info_cache:
            fund_info_cache[fund_code] = get_all_fund_info(user, fund_code)
        return fund_info_cache[fund_code]

    def _get_init_heat_score(fund_info):
        if getattr(fund_info, 'fund_type', None) != '000':
            return None
        index_code = getattr(fund_info, 'index_code', None)
        if not index_code:
            return None
        return get_latest_realtime_index_heat(user, index_code, cache=index_heat_cache)

    # 获取组合资产，构建已持有基金集合
    asset_details = get_sub_account_asset_by_name(user, sub_account_name) or []
    held_codes = {getattr(a, 'fund_code', '') for a in asset_details if getattr(a, 'fund_code', None)}
    held_group_keys = set()
    for asset in asset_details:
        info = _get_cached_fund_info(getattr(asset, "fund_code", None))
        group_key, _ = get_theme_group_key_and_label(info)
        if group_key:
            held_group_keys.add(group_key)
    logger.info(f"组合 {sub_account_name} 当前持有基金数: {len(held_codes)}")

    success_count = 0
    selected_group_keys = set()
    selected_group_representatives = {}

    for order_index, fund_item in enumerate(fund_list):
        fund_code = (fund_item or {}).get('fund_code')
        if not fund_code or fund_code in held_codes:
            continue

        fund_info = _get_cached_fund_info(fund_code)
        if not fund_info:
            continue

        group_key, group_label = get_theme_group_key_and_label(fund_info)
        if not group_key or group_key in held_group_keys:
            continue

        candidate = {
            'fund_code': fund_code,
            'fund_name': getattr(fund_info, 'fund_name', fund_code),
            'group_key': group_key,
            'group_label': group_label,
            'order_index': order_index,
            'fund_info': fund_info,
            'heat_score': _get_init_heat_score(fund_info),
            'is_index_fund': getattr(fund_info, 'fund_type', None) == '000' and bool(getattr(fund_info, 'index_code', None)),
        }
        existing = selected_group_representatives.get(group_key)
        should_replace = False
        if existing is None:
            should_replace = True
        elif candidate['is_index_fund'] and existing['is_index_fund']:
            current_heat = candidate['heat_score']
            existing_heat = existing['heat_score']
            if current_heat is not None and existing_heat is not None and abs(current_heat - existing_heat) > 1e-9:
                should_replace = current_heat > existing_heat
            elif current_heat is not None and existing_heat is None:
                should_replace = True
            elif current_heat is None and existing_heat is not None:
                should_replace = False
            else:
                should_replace = candidate['order_index'] < existing['order_index']
        else:
            should_replace = candidate['order_index'] < existing['order_index']

        if should_replace:
            selected_group_representatives[group_key] = candidate

    for candidate in selected_group_representatives.values():
        logger.info(
            f"[同主题初始化优先] {candidate['group_label']} 当前仅保留 "
            f"{candidate['fund_name']}({candidate['fund_code']})，"
            f"heat_score={candidate['heat_score'] if candidate['heat_score'] is not None else '-'}"
        )

    # 新增：估算净值（无估值则用上一交易日净值）> 5 日均值门槛
    # 删除本地 _nav5_gate，改为调用公共方法
    for fund_item in fund_list:
        try:
            fund_code = (fund_item or {}).get('fund_code')
            fund_amount = (fund_item or {}).get('amount')
            if not fund_code:
                logger.info("fund_code 缺失，跳过该条目")
                continue
            if not fund_amount or float(fund_amount) <= 0:
                logger.info(f"基金 {fund_code} 的 amount 缺失或无效，跳过该基金")
                continue

            fund_info = _get_cached_fund_info(fund_code)
            if not fund_info:
                logger.info(f"未获取到基金信息，跳过：{fund_code}")
                continue
            fund_name = getattr(fund_info, 'fund_name', fund_code)
            logger.info(f"基金信息：{fund_name}({fund_code})，可申购：{getattr(fund_info, 'can_purchase', None)}")
            group_key, group_label = get_theme_group_key_and_label(fund_info)

            # 若基金不在资产列表中，则直接购买（新增前加净值门槛）
            if fund_code not in held_codes:
                if group_key and group_key in held_group_keys:
                    logger.info(f"跳过新增：{fund_name}({fund_code})，{group_label} 已在当前持仓中存在")
                    continue
                if group_key:
                    representative = selected_group_representatives.get(group_key)
                    if representative and representative['fund_code'] != fund_code:
                        logger.info(
                            f"跳过新增：{fund_name}({fund_code})，{group_label} 本次优先保留 "
                            f"{representative['fund_name']}({representative['fund_code']}) "
                            f"(heat_score={representative['heat_score'] if representative['heat_score'] is not None else '-'})"
                        )
                        continue
                    if group_key in selected_group_keys:
                        logger.info(f"跳过新增：{fund_name}({fund_code})，{group_label} 已在本次新增中保留其他基金")
                        continue

                # 检查限购金额：如果限购金额 < 2000，则无条件直接买入
                max_purchase = getattr(fund_info, 'max_purchase', None)
                if max_purchase is not None:
                    try:
                        max_amount = float(max_purchase)
                        if max_amount < 2000:
                            logger.info(f"基金 {fund_name}({fund_code}) 限购金额 {max_amount} < 2000，触发无条件买入逻辑！")
                            # 如果请求金额大于限购金额，调整为限购金额
                            actual_amount = float(fund_amount)
                            if actual_amount > max_amount:
                                logger.info(f"请求金额 {actual_amount} 超过限额 {max_amount}，调整为 {max_amount}")
                                actual_amount = max_amount
                                
                            try:
                                if group_key:
                                    selected_group_keys.add(group_key)
                                res = commit_order(user, sub_account_no, fund_code, actual_amount)
                                if res and getattr(res, 'busin_serial_no', None):
                                    success_count += 1
                                    logger.info(f"无条件购买成功：{fund_name}({fund_code})，金额: {actual_amount}")
                                else:
                                    logger.info(f"无条件购买未成功或被系统保护跳过：{fund_name}({fund_code})")
                            except Exception as e:
                                logger.error(f"无条件购买失败：{fund_name}({fund_code})，异常: {e}")
                            
                            continue # 处理完毕，进入下一个基金
                    except (ValueError, TypeError):
                        pass

                # 候选阶段先应用五日均值过滤
                if not nav5_gate(fund_info, fund_name, fund_code, logger):
                    logger.info(f"净值未达条件，跳过候选：{fund_name}({fund_code})")
                    continue
                
                # 增加过滤条件：基金的1年收益率和半年收益率有一个小于0就跳过
                # 参考increase.py中的风控逻辑
                year_return = getattr(fund_info, "year_return", None)
                half_year_return = getattr(fund_info, "six_month_return", None)
                
                # 转换为浮点数进行比较
                year_val = float(year_return) if isinstance(year_return, (int, float)) else None
                half_year_val = float(half_year_return) if isinstance(half_year_return, (int, float)) else None
                
                # 如果年收益率 <= 0 或 半年收益率 <= 0，则跳过
                # if (year_val is not None and year_val <= 0) or (half_year_val is not None and half_year_val <= 0):
                #     logger.info(f"基金1年收益率({year_val})或半年收益率({half_year_val})小于等于0，跳过候选：{fund_name}({fund_code})")
                #     continue

                # 增加条件：基金的100日净值排名 < 20 就 continue
                rank_100 = getattr(fund_info, 'rank_100day', None)
                if rank_100 is not None:
                    try:
                        rank_100_val = float(rank_100)
                        if rank_100_val < 20:
                            logger.info(f"基金100日排名 {rank_100} < 20，跳过候选：{fund_name}({fund_code})")
                            continue
                        if rank_100_val > 90:
                            logger.info(f"基金100日排名 {rank_100} > 90，跳过候选：{fund_name}({fund_code})")
                            continue
                    except (ValueError, TypeError):
                        pass

                rank_30 = getattr(fund_info, 'rank_30day', None)
                if rank_30 is not None:
                    try:
                        if float(rank_30) < 5:
                            logger.info(f"基金30日排名 {rank_30} < 5，跳过候选：{fund_name}({fund_code})")
                            continue
                    except (ValueError, TypeError):
                        pass

                # 进行五日均值过滤（购买前最后确认）
                if not nav5_gate(fund_info, fund_name, fund_code, logger):
                    logger.info(f"未处于上升趋势（估算净值≤5日均值），跳过购买：{fund_name}({fund_code})")
                    continue

                logger.info(f"候选通过，准备购买：{fund_name}({fund_code}) [year_return={year_val}, half_year_return={half_year_val}, rank_100day={rank_100}, rank_30day={rank_30}]，金额: {fund_amount}")
                try:
                    if group_key:
                        selected_group_keys.add(group_key)
                    res = commit_order(user, sub_account_no, fund_code, float(fund_amount))
                    if res and getattr(res, 'busin_serial_no', None):
                        success_count += 1
                        logger.info(f"购买成功：{fund_name}({fund_code})，金额: {fund_amount}")
                    else:
                        logger.info(f"购买未成功或被系统保护跳过：{fund_name}({fund_code})")
                except Exception as e:
                    logger.error(f"购买失败：{fund_name}({fund_code})，异常: {e}")
                continue

            # 已持有基金：当前先不处理新增（后续补充完整加仓逻辑）
            logger.info(f"已持有基金，新增逻辑不处理：{fund_name}({fund_code})")

        except Exception as e:
            logger.error(f"处理 {fund_item} 失败: {e}")

    logger.info(f"新增完成：{customer_name} 成功执行 {success_count} 次购买操作")
    return success_count > 0


if __name__ == "__main__":
    try:
        increase_funds(
            DEFAULT_USER,
            "海外基金组合",
            fund_list=[
                {"fund_code": "016702", "fund_name": "银华海外数字经济量化选股混合发起式(QDII)C", "amount": 5000.0},
                {"fund_code": "006105", "fund_name": "宏利印度股票(QDII)", "amount": 5000.0},
                {"fund_code": "161226", "fund_name": "国投瑞银白银期货(LOF)A", "amount": 5000.0},
                {"fund_code": "017873", "fund_name": "汇添富香港优势精选混合(QDII)C", "amount": 5000.0},
                {"fund_code": "019449", "fund_name": "摩根日本精选股票(QDII)C", "amount": 5000.0}
            ],
            total_budget=1000000.0,
        )
        logging.info(f"用户 {DEFAULT_USER.customer_name} 新增操作完成")
    except Exception as e:
        logging.error(f"测试用户处理失败：{str(e)}")
