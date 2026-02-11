
import sys
import os
import logging
from datetime import datetime
from typing import List, Dict, Any

# Add project root to path
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.service.银行卡账户.bankAccoutService import getMaxhqbBank
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name, get_asset_list_of_sub
from src.API.组合管理.SubAccountMrg import getSubAccountList, getSubAccountNoByName
from src.service.大数据.加仓风向标服务 import get_fund_investment_indicators
from src.API.定投计划管理.SmartPlan import getFundPlanList
from src.API.交易管理.trade import get_trades_list
from src.service.基金信息.基金信息 import get_all_fund_info
import yaml
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ComprehensiveReport")

def load_swarm_config(yaml_path: str) -> List[Dict]:
    """Load Swarm configuration from s.yaml"""
    if not os.path.exists(yaml_path):
        return []
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        try:
            config = yaml.safe_load(f)
            vars_config = config.get('vars', {})
            payload_str = vars_config.get('fixed_ratio_redeem_payload')
            if payload_str:
                try:
                    data = json.loads(payload_str)
                    return data.get('fundcodelist', [])
                except:
                    pass
            return vars_config.get('fixed_ratio_redeem_config', {}).get('fundcodelist', [])
        except:
            return []

def get_today_trades_firepower(user, fund_codes: set) -> Dict[str, float]:
    """Get today's actual trading amount for specific funds"""
    firepower_map = {}
    try:
        # Fetch last week's trades to cover today
        trades = get_trades_list(user, date_type="5")
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        for t in trades:
            # Date check
            date_val = str(getattr(t, 'strike_start_date', '') or getattr(t, 'apply_work_day', '') or '')
            if not date_val.startswith(today_str):
                continue
            
            # Status check
            status = str(getattr(t, 'app_state_text', '') or getattr(t, 'status', ''))
            if any(x in status for x in ["撤单", "失败", "无效"]):
                continue
                
            # Type check (Buy/Invest only)
            b_type = str(getattr(t, 'business_type', '')).strip()
            if any(x in b_type for x in ["赎回", "分红", "转换出", "卖出"]):
                continue
                
            # Amount cleaning
            raw_amount = getattr(t, 'amount', 0) or getattr(t, 'apply_amount', 0) or 0
            try:
                if isinstance(raw_amount, str):
                    import re
                    cleaned = re.sub(r'[^\d\.]', '', raw_amount)
                    amount = float(cleaned)
                else:
                    amount = float(raw_amount)
            except:
                amount = 0.0
                
            # Code check
            f_code = getattr(t, 'fund_code', '') or getattr(t, 'product_code', '')
            if f_code in fund_codes and amount > 0:
                firepower_map[f_code] = firepower_map.get(f_code, 0.0) + amount
                
    except Exception as e:
        logger.warning(f"Failed to fetch trades: {e}")
        
    return firepower_map

def generate_report(user):
    logger.info("Starting comprehensive report generation...")
    report_lines = []
    
    # 1. Overview
    try:
        user_with_bank = getMaxhqbBank(user)
        bank_card = getattr(user_with_bank, "max_hqb_bank", None)
        hqb_balance = 0.0
        if bank_card:
            hqb_balance = float(getattr(bank_card, "BankAvaVol", 0) or getattr(bank_card, "CurrentRealBalance", 0))
    except:
        hqb_balance = 0.0

    report_lines.append(f"# 深度量化投资系统综合评估报告")
    report_lines.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append(f"**投资人**: {user.customer_name}")
    report_lines.append("")
    
    report_lines.append("## 1. 资金总览 (Capital Overview)")
    report_lines.append(f"- **弹药库 (活期宝)**: ¥{hqb_balance:,.2f}")
    
    # 2. Swarm Strategy
    report_lines.append("")
    report_lines.append("## 2. 蜂群战术 (Swarm Strategy)")
    swarm_funds_config = load_swarm_config(os.path.join(root_dir, 's.yaml'))
    swarm_codes = set(item.get('fundcode') for item in swarm_funds_config)
    
    # Get firepower
    today_firepower = get_today_trades_firepower(user, swarm_codes)
    total_firepower = sum(today_firepower.values())
    
    # Get holdings (Need to scan all sub-accounts or just specific ones? Swarm usually spreads across main/sub)
    # We will approximate by scanning all sub-accounts for these funds
    total_swarm_holding = 0.0
    swarm_details = []
    
    # Pre-fetch sub-accounts
    sub_accounts = []
    try:
        sub_resp = getSubAccountList(user)
        if sub_resp.Success:
            sub_accounts = sub_resp.Data
    except:
        pass
        
    # Build fund info map
    for item in swarm_funds_config:
        code = item.get('fundcode')
        name = "未知基金"
        try:
            info = get_all_fund_info(user, code)
            if info: name = info.fund_name
        except: pass
        
        # Get active plans
        active_plans = 0
        try:
            plans = getFundPlanList(code, user)
            active_plans = sum(1 for p in plans if str(p.planState) == "0")
        except: pass
        
        # Get holding for this fund across all accounts (simplified)
        # Note: This might be slow if we query asset for every fund. 
        # Better: Query all assets from all subs first.
        # But for now, let's just query main + known subs? 
        # Or better, let's skip precise holding per fund here to save time, 
        # OR iterate all subs once and map assets.
        
        firepower = today_firepower.get(code, 0.0)
        swarm_details.append({
            "code": code,
            "name": name,
            "stop_rate": item.get('stoprate'),
            "active_plans": active_plans,
            "firepower": firepower
        })

    # Calculate total swarm holdings (iterate all sub-accounts)
    all_assets_map = {} # code -> amount
    
    # Main account assets (usually empty for this user but check)
    # Sub accounts
    target_subs = ["主账户"] + [s.sub_account_name for s in sub_accounts]
    
    logger.info("Scanning assets across portfolios...")
    for sub_name in target_subs:
        sub_no = ""
        if sub_name != "主账户":
            sub_no = getSubAccountNoByName(user, sub_name)
        
        try:
            assets = get_asset_list_of_sub(user, sub_no)
            for a in assets:
                all_assets_map[a.fund_code] = all_assets_map.get(a.fund_code, 0.0) + float(a.asset_value)
        except:
            pass

    # Update swarm holdings
    for d in swarm_details:
        d['holding'] = all_assets_map.get(d['code'], 0.0)
        total_swarm_holding += d['holding']

    report_lines.append(f"- **战斗单元**: {len(swarm_codes)} 个")
    report_lines.append(f"- **策略总持仓**: ¥{total_swarm_holding:,.2f}")
    report_lines.append(f"- **今日火力**: ¥{total_firepower:,.2f}")
    report_lines.append("")
    report_lines.append("| 代码 | 名称 | 止盈阈值 | 持仓市值 | 活跃计划 | 今日火力 | 状态 |")
    report_lines.append("|---|---|---|---|---|---|---|")
    for d in swarm_details:
        status = "进攻" if d['active_plans'] > 0 else "休整"
        if d['holding'] > 5000: status += "/重仓"
        report_lines.append(f"| {d['code']} | {d['name'][:8]} | {d['stop_rate']}% | ¥{d['holding']:,.2f} | {d['active_plans']} | ¥{d['firepower']:,.2f} | {status} |")

    # 3. Dragon Strategies
    report_lines.append("")
    report_lines.append("## 3. 龙系策略 (Dragon Strategies)")
    
    dragon_portfolios = ["见龙在田", "飞龙在天"]
    for port_name in dragon_portfolios:
        sub_no = getSubAccountNoByName(user, port_name)
        assets = []
        if sub_no:
            assets = get_asset_list_of_sub(user, sub_no)
        
        total_val = sum(float(a.asset_value) for a in assets)
        count = len(assets)
        
        report_lines.append(f"### {port_name}")
        report_lines.append(f"- **总资产**: ¥{total_val:,.2f}")
        report_lines.append(f"- **持仓数量**: {count} 只")
        if count > 0:
            # List top 3 holdings
            assets.sort(key=lambda x: float(x.asset_value), reverse=True)
            top3 = assets[:3]
            top_str = ", ".join([f"{a.fund_name}({float(a.asset_value):.0f})" for a in top3])
            report_lines.append(f"- **重仓**: {top_str}...")

    # 4. Custom Portfolios
    report_lines.append("")
    report_lines.append("## 4. 自定义组合 (Custom Portfolios)")
    custom_ports = ["海外基金组合", "快速止盈", "黄金多利", "黄金异次元"]
    
    report_lines.append("| 组合名称 | 总资产 | 持仓数 | 主要方向 |")
    report_lines.append("|---|---|---|---|")
    
    for port_name in custom_ports:
        sub_no = getSubAccountNoByName(user, port_name)
        assets = []
        if sub_no:
            assets = get_asset_list_of_sub(user, sub_no)
        total_val = sum(float(a.asset_value) for a in assets)
        
        direction = "混合"
        if "黄金" in port_name: direction = "黄金/避险"
        elif "海外" in port_name: direction = "QDII/全球"
        elif "止盈" in port_name: direction = "高频交易"
        
        report_lines.append(f"| {port_name} | ¥{total_val:,.2f} | {len(assets)} | {direction} |")

    # 5. Wind Vane Signals
    report_lines.append("")
    report_lines.append("## 5. 加仓风向标 (Market Signals)")
    report_lines.append("> 基于大数据排名的潜在加仓机会")
    
    try:
        indicators = get_fund_investment_indicators()
        # Sort by rank (lower is better)
        indicators.sort(key=lambda x: getattr(x, 'product_rank', 9999))
        
        top_picks = indicators[:10]
        report_lines.append("| 排名 | 代码 | 名称 | 类型 | 估值状态 | 建议 |")
        report_lines.append("|---|---|---|---|---|---|")
        
        for idx, item in enumerate(top_picks, 1):
            name = getattr(item, 'fund_name', '')
            code = getattr(item, 'fund_code', '')
            ftype = "指数" if getattr(item, 'fund_type', '') == '000' else "主动"
            # We don't have real-time valuation here easily, but we can check if we hold it
            is_held = code in all_assets_map
            advice = "关注"
            if is_held: advice = "已持仓/加仓"
            else: advice = "建仓机会"
            
            report_lines.append(f"| {idx} | {code} | {name[:8]} | {ftype} | - | {advice} |")
            
    except Exception as e:
        report_lines.append(f"获取风向标数据失败: {e}")

    # 6. Summary & Prediction
    report_lines.append("")
    report_lines.append("## 6. 系统综合研判 (System Evaluation)")
    
    total_invested = total_swarm_holding + sum(all_assets_map.values()) # This might double count swarm, wait.
    # Recalculate total invested properly
    total_invested = sum(all_assets_map.values())
    
    total_capital = hqb_balance + total_invested
    position_ratio = (total_invested / total_capital * 100) if total_capital > 0 else 0
    
    report_lines.append(f"- **总权益**: ¥{total_capital:,.2f}")
    report_lines.append(f"- **当前仓位**: {position_ratio:.2f}%")
    
    status_eval = "攻守平衡"
    if position_ratio > 70: status_eval = "全面进攻"
    elif position_ratio < 30: status_eval = "防守/蛰伏"
    
    report_lines.append(f"- **系统状态**: **{status_eval}**")
    
    report_lines.append("")
    report_lines.append("### 收益潜力预估")
    report_lines.append("1. **蜂群系统**: 维持高频定投，在震荡市中通过低止盈阈值(1%-5%)不断收割波动收益。今日火力强劲，预计短期内会有止盈信号触发。")
    report_lines.append("2. **龙系策略**: '飞龙在天'与'见龙在田'作为中长期主力，承接风向标筛选出的优质资产，享受趋势上涨红利。")
    report_lines.append("3. **黄金组合**: 提供底层安全垫，对冲权益类资产风险。")
    
    report_lines.append("")
    report_lines.append("**建议**: ")
    if hqb_balance < 100000:
        report_lines.append("- ⚠️ **警告**: 弹药库水位较低，建议补充流动性以维持蜂群定投的持续性。")
    else:
        report_lines.append("- ✅ 弹药充足，可继续保持当前策略运行。")

    # Output to file
    output_path = os.path.join(root_dir, 'reports', f'comprehensive_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md')
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))
        
    print(f"Report generated: {output_path}")
    print("\n".join(report_lines))

if __name__ == "__main__":
    generate_report(DEFAULT_USER)
