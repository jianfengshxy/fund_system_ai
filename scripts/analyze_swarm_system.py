
import sys
import os
import logging
import yaml
import json
from typing import List, Dict

# 添加项目根目录到 Python 路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.定投计划管理.SmartPlan import getFundPlanList
from src.service.资产管理.get_fund_asset_detail import get_fund_asset_detail
from src.service.基金信息.基金信息 import get_all_fund_info
from src.service.银行卡账户.bankAccoutService import getMaxhqbBank
from src.API.组合管理.SubAccountMrg import getSubAccountList
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SwarmAnalysis")

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

def analyze_swarm_system(user):
    logger.info(f"========== 开始分析蜂群投资系统 ==========")
    logger.info(f"用户: {user.customer_name} ({user.account})")
    
    # 1. 获取弹药库信息 (活期宝)
    try:
        user_with_bank = getMaxhqbBank(user)
        bank_card = getattr(user_with_bank, "max_hqb_bank", None)
        # bank_card 是 HqbBank 对象
        hqb_balance = 0.0
        if bank_card:
            # 使用 BankAvaVol 或 CurrentRealBalance
            hqb_balance = float(getattr(bank_card, "BankAvaVol", 0) or getattr(bank_card, "CurrentRealBalance", 0))
            
        logger.info(f"弹药库(活期宝)余额: {hqb_balance:.2f} 元")
    except Exception as e:
        logger.error(f"获取活期宝信息失败: {e}")
        hqb_balance = 0.0

    # 2. 读取蜂群配置
    yaml_file = os.path.join(root_dir, 's.yaml')
    config = load_config(yaml_file)
    fund_list = config.get('fundcodelist', [])
    
    if not fund_list:
        logger.warning("未找到蜂群(基金)配置列表")
        return

    logger.info(f"监测到 {len(fund_list)} 只战斗蜂群 (指定止盈基金)")
    
    # 3. 遍历分析每一只蜂群
    total_swarm_holding = 0.0
    total_daily_firepower = 0.0 # 每日理论最大定投金额
    swarm_details = []

    # 预先获取所有子账户列表，方便后续查找
    sub_accounts = []
    try:
        sub_resp = getSubAccountList(user)
        if sub_resp.Success:
            sub_accounts = sub_resp.Data
    except Exception as e:
        logger.warning(f"获取子账户列表失败: {e}")

    for item in fund_list:
        fund_code = item.get('fundcode')
        stop_rate = float(item.get('stoprate', 0.0))
        
        fund_name = "未知基金"
        try:
            info = get_all_fund_info(user, fund_code)
            if info:
                fund_name = info.fund_name
        except:
            pass
            
        # A. 检查火力配置 (定投计划)
        plans = []
        try:
            plans = getFundPlanList(fund_code, user)
        except Exception as e:
            logger.warning(f"获取基金 {fund_code} 定投计划失败: {e}")
            
        active_plans_count = 0
        total_plans_count = 0
        fund_firepower = 0.0
        potential_firepower = 0.0
        
        target_sub_accounts = set()
        
        for p in plans:
            # 收集该基金关联的定投计划所在的子账户
            # 如果 subAccountNo 为空，表示主账户，用 "" 表示
            target_sub_accounts.add(p.subAccountNo if p.subAccountNo else "")

            total_plans_count += 1
            
            # 计算单笔火力
            amount = float(p.amount)
            p_power = 0.0
            period_type = str(p.periodType)
            if period_type == "4" or period_type == "0": # 日
                p_power = amount
            elif period_type == "1": # 周
                p_power = amount / 5.0
            elif period_type == "2": # 双周
                p_power = amount / 10.0
            elif period_type == "3": # 月
                p_power = amount / 22.0
            else:
                p_power = amount

            # 统计潜在火力 (排除已终止的，假设 '2' 是终止)
            if str(p.planState) != "2":
                potential_firepower += p_power

            # 统计实际火力 (进行中)
            if str(p.planState) == "1":
                active_plans_count += 1
                fund_firepower += p_power
            
        total_daily_firepower += fund_firepower

        # B. 检查战果 (仅统计定投计划关联组合内的资产)
        fund_holding = 0.0
        found_in_subs = []
        
        if not target_sub_accounts:
            # 如果没有定投计划，是否应该搜索所有？用户说"只看定投账户组合"，暗示只看相关的。
            # 如果没有计划，那么持仓也应该视为0（或者用户手动买入的非定投资产不计入蜂群系统）
            pass
        else:
            for sub_no in target_sub_accounts:
                try:
                    # 查找子账户名称
                    if not sub_no:
                        sub_name = "主账户"
                    else:
                        sub_name = sub_no
                        for s in sub_accounts:
                            if s.sub_account_no == sub_no:
                                sub_name = s.sub_account_name
                                break
                    
                    assets = get_asset_list_of_sub(user, sub_no)
                    for asset in assets:
                        if asset.fund_code == fund_code:
                            fund_holding += float(asset.asset_value)
                            found_in_subs.append(sub_name)
                except Exception as e:
                    logger.warning(f"获取子账户 {sub_no} 资产失败: {e}")
        
        # 移除主账户搜索逻辑
        # ...
            
        total_swarm_holding += fund_holding
        
        status_desc = "蛰伏"
        if active_plans_count > 0:
            status_desc = "活跃"
        if fund_holding > 1000:
            status_desc += " | 采蜜中"
            
        swarm_details.append({
            "code": fund_code,
            "name": fund_name,
            "stop_rate": stop_rate,
            "holding": fund_holding,
            "active_plans": active_plans_count,
            "total_plans": total_plans_count,
            "daily_power": fund_firepower,
            "potential_power": potential_firepower,
            "location": ",".join(found_in_subs)
        })

    # 4. 生成报告
    print("\n" + "="*80)
    print(f"【蜂群式投资系统综合分析报告】")
    print("="*80)
    print(f"用户: {user.customer_name}")
    print(f"弹药库(活期宝): {hqb_balance:,.2f} 元")
    print(f"蜂群规模: {len(fund_list)} 个战斗单元")
    print(f"当前总战果(策略持仓): {total_swarm_holding:,.2f} 元 (仅统计定投计划关联组合)")
    print(f"当前日均火力: {total_daily_firepower:,.2f} 元/日 (活跃计划)")
    
    # 计算潜在总火力
    total_potential_power = sum(item['potential_power'] for item in swarm_details)
    print(f"潜在日均火力: {total_potential_power:,.2f} 元/日 (所有非终止计划)")
    
    # 计算资金利用率指标
    total_capital = hqb_balance + total_swarm_holding
    utilization_rate = (total_swarm_holding / total_capital * 100) if total_capital > 0 else 0
    
    print(f"资金利用率(仓位): {utilization_rate:.2f}%")
    print("-" * 80)
    print(f"{'代码':<8} {'名称':<12} {'止盈':<5} {'持仓市值':<10} {'活跃/总计划':<10} {'火力(元/日)':<10} {'状态'}")
    print("-" * 80)
    
    for item in swarm_details:
        name = item['name'][:8] + ".." if len(item['name']) > 8 else item['name']
        status = "进攻" if item['active_plans'] > 0 else "休整"
        if item['holding'] < 100: status += "/空仓"
        elif item['holding'] > 5000: status += "/重仓"
        
        plan_str = f"{item['active_plans']}/{item['total_plans']}"
        power_str = f"{item['daily_power']:.0f}/{item['potential_power']:.0f}"
        
        print(f"{item['code']:<8} {name:<12} {item['stop_rate']}%   {item['holding']:<10.2f} {plan_str:<10} {power_str:<10} {status}")
        
    print("-" * 80)
    print("【系统评价】")
    if utilization_rate < 30:
        print("当前状态: 整体处于[蛰伏/防守]阶段。弹药充足，蜂群已回收大部分利润，等待下一次出击信号。")
    elif utilization_rate > 70:
        print("当前状态: 整体处于[全面进攻]阶段。大部分资金已投入战场，正在积极采蜜。")
    else:
        print("当前状态: 整体处于[攻守平衡]阶段。部分蜂群正在采蜜，部分已回收，节奏良好。")
        
    print(f"\n专业点评: 您的系统配置了 {len(fund_list)} 个低止盈阈值(1%-5%)的战斗单元。")
    print("结合 increase.py 的均线/排名风控，这套系统能够实现'不见兔子不撒鹰'。")
    print("当前持仓与弹药库的比例反映了市场环境对策略的触发情况，")
    print("请重点关注'重仓'状态的基金，它们可能接近止盈点或正在经历回调补仓。")
    print("="*60 + "\n")

if __name__ == "__main__":
    analyze_swarm_system(DEFAULT_USER)
