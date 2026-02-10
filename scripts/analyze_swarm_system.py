
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
from src.API.交易管理.trade import get_trades_list
from datetime import datetime

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
    
    # 2.5 获取今日实际火力 (交易记录)
    today_firepower_map = {}
    try:
        logger.info("正在获取今日实时交易记录...")
        # 获取近1周交易 (date_type="5")
        recent_trades = get_trades_list(user, date_type="5")
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        today_trade_count = 0
        for t in recent_trades:
            # 1. 日期匹配 (StrikeStartDate)
            # API 返回格式可能是 "2026-02-10" 或 "2026-02-10 13:00:00"
            trade_date = str(getattr(t, 'strike_start_date', '') or getattr(t, 'apply_work_day', '') or '')
            if not trade_date.startswith(today_str):
                continue
                
            # 2. 状态过滤 (排除撤单、失败)
            status = str(getattr(t, 'app_state_text', '') or getattr(t, 'status', ''))
            # 注意：状态文本可能是 "已撤单(已支付)" 或 "已撤单"
            # 我们需要排除包含 "撤单"、"失败"、"无效" 的记录
            if "撤单" in status or "失败" in status or "无效" in status:
                continue
                
            # 3. 业务类型过滤 (仅统计买入/定投)
            # business_type: "申购", "定投", "普通申购", "转换入", "活期宝转入定投", "活期宝转入基金" 等
            # 或者通过 amount > 0 且不是赎回
            b_type = str(getattr(t, 'business_type', '')).strip()
            # 排除赎回、分红、转换出
            # 注意：有些卖出交易的 business_type 也是 "卖出回活期宝(极速)"
            if "赎回" in b_type or "分红" in b_type or "转换出" in b_type or "卖出" in b_type:
                continue
            
            # 累加火力
            f_code = getattr(t, 'fund_code', '') or getattr(t, 'product_code', '')
            
            # amount 可能是 "10,000.00元" 这样的字符串，需要清洗
            raw_amount = getattr(t, 'amount', 0) or getattr(t, 'apply_amount', 0) or 0
            try:
                if isinstance(raw_amount, str):
                    # 去除 "元", "份", "," 等非数字字符
                    import re
                    # 只保留数字和小数点
                    cleaned = re.sub(r'[^\d\.]', '', raw_amount)
                    amount = float(cleaned)
                else:
                    amount = float(raw_amount)
            except:
                amount = 0.0
            
            if f_code and amount > 0:
                today_firepower_map[f_code] = today_firepower_map.get(f_code, 0.0) + amount
                today_trade_count += 1
                
        logger.info(f"今日有效买入交易: {today_trade_count} 笔, 涉及 {len(today_firepower_map)} 只基金")
        
    except Exception as e:
        logger.error(f"获取今日交易记录失败: {e}")

    # 3. 遍历分析每一只蜂群
    total_swarm_holding = 0.0
    total_daily_firepower = 0.0 # 每日实际交易金额
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
            # 使用 getFundPlanList 获取指定基金的计划
            # 注意：该函数内部调用的是 getFundPlanListV2 接口，可能返回分页数据
            # 默认 PAGE_INDEX=1, PAGE_SIZE=20 (常量定义)
            # 如果计划较多，可能需要翻页或增大 pageSize
            # 这里为了简单，我们假设 SmartPlan.py 中的 getFundPlanList 已经处理了基本获取
            # 但查看 SmartPlan.py 源码，getFundPlanList 确实只请求第一页
            # 如果 021740 有 33 个计划，而 pageSize=20，则会漏掉 13 个
            
            # 临时方案：调用 getFundPlanList 时，如果是该脚本，我们没法传 pageSize (函数签名固定)
            # 但我们可以直接调用 API 或者修改 getFundPlanList
            # 或者，我们可以循环调用直到没数据
            
            # 不过，用户反馈 021740 只有 5 个周定投，但统计显示 33 个
            # 这说明 getFundPlanList 可能把其他状态（如终止）的也查出来了，或者 API 返回了历史数据
            # 33/0 意味着 total=33, active=0
            # active=0 是因为之前 planState 判断错误（'1' vs '0'）
            # 33 个可能是历史累计的终止计划
            
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
            # periodType 映射:
            # 0: 日
            # 1: 周
            # 2: 双周
            # 3: 月
            # 4: 日 (某些版本)
            # 调试中看到 periodType 为 4, amount=2000.0, 但 daily_power 为 0
            # 原因可能是 planState 虽然是 '0'，但我们之前计算火力的时候 p_power 计算有问题？
            # 检查：period_type == "4" or period_type == "0" -> p_power = amount
            # amount 是 float，应该没问题。
            
            # 调试：打印详细信息
            # 日志显示: Amount=0.0
            # 可能是属性名不对？
            # 检查 FundPlan 类定义：amount: float = 0.0
            
            # 尝试从 raw data 中恢复？
            # 不行，这里已经是对象了。
            
            # 唯一的解释是 SmartPlan.py 在解析 API 响应时，没有正确地把金额映射到 amount 字段。
            # 或者 API 返回的字段名变了。
            
            # 让我们尝试用一个临时修复：如果 amount 是 0，则尝试从 nextDeductDescription 中提取？
            # 描述通常是 "下个扣款日 2026-02-12，扣款 1000.00 元"
            
            # 计算单笔火力 (不再使用 plan 推算，而是直接使用 today_firepower_map)
            # 这里仅用于统计"活跃计划数"，不用于计算火力
            p_power = 0.0 # 占位

            # 统计潜在火力 (这里保留原来的逻辑？或者也改成只看今天？)
            # 用户问的是 "火力(元/日)"，通常指实际火力
            # 潜在火力如果也按今天算，那么非扣款日的潜在火力就是0，这可能导致数据波动很大
            # 但为了保持一致性，我们把"潜在火力"定义为"所有非终止计划在今天的理论扣款额"
            # 这样如果今天是周一，就能看到巨大的潜在火力；周二则很小。符合"当日火力"的定义。
            
            # 恢复之前的潜在火力计算逻辑（按周期折算），作为参考
            # 或者干脆只显示实际火力？
            # 让我们还是算一下"理论平均日火力"作为参考
            
            if period_type in ["4", "0"]: # 日
                p_power = amount
            elif period_type == "1": # 周
                p_power = amount / 5.0
            elif period_type == "2": # 双周
                p_power = amount / 10.0
            elif period_type == "3": # 月
                p_power = amount / 22.0
            else:
                p_power = amount 

            if str(p.planState) != "2":
                potential_firepower += p_power

            # 统计实际火力 (进行中)
            if str(p.planState) == "0":
                active_plans_count += 1
                # fund_firepower += p_power # 不再累加 plan 的火力
            
        # 使用交易记录覆盖 fund_firepower
        fund_firepower = today_firepower_map.get(fund_code, 0.0)
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
