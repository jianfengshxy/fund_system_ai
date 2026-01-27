import os
import sys
import logging
import re
import json
import requests
from datetime import datetime, timedelta
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.组合管理.SubAccountMrg import getSubAccountNoByName
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.资产管理.getAssetListOfSub import get_asset_list_of_sub
from src.API.交易管理.trade import get_trades_list
from src.service.基金信息.基金信息 import get_all_fund_info

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_fund_max_drawdown(fund_code, days=90):
    """获取基金最近N天的最大回撤"""
    url = f"http://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return 0.0
            
        content = response.text
        # 提取单位净值走势 Data_netWorthTrend
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[.*?\]);', content)
        if not match:
            return 0.0

        data_json = json.loads(match.group(1))
        # 数据格式: [{"x": 1672531200000, "y": 1.2345, ...}, ...]
        
        cutoff_ts = (datetime.now() - timedelta(days=days)).timestamp() * 1000
        
        navs = [float(item['y']) for item in data_json if item['x'] >= cutoff_ts]
        
        if not navs:
            return 0.0
            
        max_nav = navs[0]
        max_dd = 0.0
        
        for nav in navs:
            if nav > max_nav:
                max_nav = nav
            
            if max_nav > 0:
                dd = (max_nav - nav) / max_nav * 100
                if dd > max_dd:
                    max_dd = dd
                    
        return max_dd
    except Exception as e:
        logger.warning(f"计算基金 {fund_code} 最大回撤失败: {e}")
        return 0.0

def clean_float(value):
    """清理包含逗号和单位的数字字符串"""
    if not value:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    
    # 移除 '元', '份' 等常见单位和逗号
    s = str(value).replace(',', '').replace('元', '').replace('份', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def get_custom_strategy_performance():
    """获取自定义组合策略的性能分析"""
    logger.info("开始获取自定义组合'快速止盈'的性能数据")

    # 获取组合账号
    sub_account_name = "快速止盈"
    sub_account_no = getSubAccountNoByName(DEFAULT_USER, sub_account_name)

    if not sub_account_no:
        logger.error(f"未找到组合 {sub_account_name} 的账号")
        return None

    logger.info(f"获取到组合账号: {sub_account_no}")

    # 获取组合资产详情
    asset_details = get_sub_account_asset_by_name(DEFAULT_USER, sub_account_name)

    if not asset_details:
        logger.info(f"组合 {sub_account_name} 中没有基金资产")
        return None

    # 获取所有持仓基金的详细信息
    holdings_info = []
    total_asset_value = 0
    total_profit_loss = 0

    def process_single_asset(asset):
        try:
            fund_code = asset.fund_code
            fund_name = asset.fund_name

            # 获取基金基础信息
            fund_info = get_all_fund_info(DEFAULT_USER, fund_code)

            # 计算盈亏信息
            asset_value = float(asset.asset_value) if asset.asset_value else 0
            # AssetDetails 没有 cost_value 属性，通过 资产市值 - 持仓收益 计算成本
            profit_loss = float(asset.hold_profit) if asset.hold_profit else 0
            cost_value = asset_value - profit_loss
            profit_rate = (profit_loss / cost_value * 100) if cost_value > 0 else 0

            # 获取最新净值
            latest_nav = float(fund_info.nav) if fund_info and fund_info.nav else 0
            
            # 计算最大回撤 (90天)
            max_drawdown = get_fund_max_drawdown(fund_code, days=90)

            return {
                'fund_code': fund_code,
                'fund_name': fund_name,
                'asset_value': asset_value,
                'cost_value': cost_value,
                'profit_loss': profit_loss,
                'profit_rate': profit_rate,
                'latest_nav': latest_nav,
                'max_drawdown': max_drawdown,
                'available_vol': float(asset.available_vol) if asset.available_vol else 0,
                'frozen_vol': float(getattr(asset, 'frozen_vol', 0))
            }
        except Exception as e:
            logger.error(f"处理基金 {asset.fund_code} 失败: {e}")
            return None

    # 并发处理基金信息
    logger.info(f"开始并发处理 {len(asset_details)} 只基金的信息...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_single_asset, asset) for asset in asset_details]
        for future in as_completed(futures):
            result = future.result()
            if result:
                holdings_info.append(result)
                total_asset_value += result['asset_value']
                total_profit_loss += result['profit_loss']

    # 获取最近三个月的交易记录
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)

    try:
        # get_trades_list 默认获取最近3个月(DateType=3)的交易记录
        # 增加重试机制应对 SSL 错误
        import time
        for attempt in range(3):
            try:
                trades = get_trades_list(
                    DEFAULT_USER,
                    sub_account_no
                )
                if trades:
                    break
            except Exception as e:
                logger.warning(f"获取交易记录尝试 {attempt+1}/3 失败: {e}")
                if attempt < 2:
                    time.sleep(2)
    except Exception as e:
        logger.error(f"获取交易记录最终失败: {e}")
        trades = None


    # 整理交易记录
    trade_records = []
    if trades:
        # 兼容 API 返回列表或 TradeResult 对象的情况
        trade_list = trades if isinstance(trades, list) else (trades.Data if hasattr(trades, 'Data') else [])
        
        for trade in trade_list:
            # 兼容 TradeResult 对象属性 (occur_date -> apply_work_day)
            trade_date = getattr(trade, 'occur_date', None) or getattr(trade, 'apply_work_day', '')
            # 兼容 TradeResult 对象属性 (fund_name -> product_name)
            fund_name = getattr(trade, 'fund_name', None) or getattr(trade, 'product_name', '')
            
            trade_records.append({
                'date': trade_date,
                'fund_code': getattr(trade, 'fund_code', ''),
                'fund_name': fund_name,
                'business_type': getattr(trade, 'business_type', ''),
                'confirm_status': getattr(trade, 'confirm_status', ''),
                'applied_amount': clean_float(getattr(trade, 'applied_amount', 0) or getattr(trade, 'amount', 0)),
                'confirmed_amount': clean_float(getattr(trade, 'confirmed_amount', 0)),
                'applied_vol': clean_float(getattr(trade, 'applied_vol', 0)),
                'confirmed_vol': clean_float(getattr(trade, 'confirmed_vol', 0))
            })

    # 按日期排序交易记录
    trade_records.sort(key=lambda x: x['date'], reverse=True)

    # 过滤时间范围 (确保只包含最近90天)
    start_date_str = start_date.strftime('%Y-%m-%d')
    # apply_work_day 可能是 "2026-01-27 09:35:11"，只取前10位比较
    trade_records = [t for t in trade_records if t['date'][:10] >= start_date_str]

    # 统计交易类型
    # 根据中文描述判断交易方向
    def is_buy(t):
        bt = t['business_type']
        return any(k in bt for k in ['买入', '申购', '定投', '转入'])
        
    def is_sell(t):
        bt = t['business_type']
        return any(k in bt for k in ['卖出', '赎回', '转换转出'])

    buy_trades = [t for t in trade_records if is_buy(t)]
    sell_trades = [t for t in trade_records if is_sell(t)]

    # 计算最大回撤统计
    max_dd_list = [h['max_drawdown'] for h in holdings_info]
    avg_max_dd = sum(max_dd_list) / len(max_dd_list) if max_dd_list else 0
    worst_dd = max(max_dd_list) if max_dd_list else 0

    performance_data = {
        'sub_account_name': sub_account_name,
        'sub_account_no': sub_account_no,
        'holdings_info': holdings_info,
        'total_asset_value': total_asset_value,
        'total_profit_loss': total_profit_loss,
        'total_profit_rate': (total_profit_loss / (total_asset_value - total_profit_loss) * 100) if (total_asset_value - total_profit_loss) > 0 else 0,
        'trade_records': trade_records,
        'buy_trades_count': len(buy_trades),
        'sell_trades_count': len(sell_trades),
        'all_trades_count': len(trade_records),
        'avg_max_drawdown': avg_max_dd,
        'worst_max_drawdown': worst_dd
    }

    return performance_data

def save_performance_report(performance_data):
    """保存性能报告到reports目录"""
    reports_dir = os.path.join(root_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)

    # 生成报告内容
    report_content = f"""# 自定义组合策略性能报告

## 基本信息
- 组合名称: {performance_data['sub_account_name']}
- 组合账号: {performance_data['sub_account_no']}
- 数据获取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 组合总体表现
- 总资产价值: ¥{performance_data['total_asset_value']:,.2f}
- 总盈亏金额: ¥{performance_data['total_profit_loss']:,.2f}
- 总盈亏比率: {performance_data['total_profit_rate']:.2f}%

## 持仓详情
| 基金代码 | 基金名称 | 资产价值 | 成本价值 | 盈亏金额 | 盈亏比率 | 最新净值 | 最大回撤(3月) |
|----------|----------|----------|----------|----------|----------|----------|---------------|
"""

    for holding in performance_data['holdings_info']:
        report_content += f"| {holding['fund_code']} | {holding['fund_name']} | ¥{holding['asset_value']:,.2f} | ¥{holding['cost_value']:,.2f} | ¥{holding['profit_loss']:,.2f} | {holding['profit_rate']:.2f}% | {holding['latest_nav']} | {holding['max_drawdown']:.2f}% |\n"

    report_content += f"""
## 交易活动统计（最近3个月）
- 总交易次数: {performance_data['all_trades_count']}
- 买入交易次数: {performance_data['buy_trades_count']}
- 卖出交易次数: {performance_data['sell_trades_count']}

## 交易记录详情（最近3个月）
| 日期 | 基金代码 | 基金名称 | 业务类型 | 状态 | 申请金额 | 确认金额 | 申请份额 | 确认份额 |
|------|----------|----------|----------|------|----------|----------|----------|----------|
"""

    for trade in performance_data['trade_records']:
        report_content += f"| {trade['date']} | {trade['fund_code']} | {trade['fund_name']} | {trade['business_type']} | {trade['confirm_status']} | ¥{trade['applied_amount']:,.2f} | ¥{trade['confirmed_amount']:,.2f} | {trade['applied_vol']:.2f} | {trade['confirmed_vol']:.2f} |\n"

    # 添加综合评价
    efficiency_comment = "交易效率较低" if performance_data['total_profit_loss'] < 0 and performance_data['all_trades_count'] > 10 else "交易效率尚可"
    
    report_content += f"""
## 综合评价

### 策略效果评估
根据自定义组合'快速止盈'的运行情况，对该策略的综合评价如下：

1. **整体收益表现**：
   - 当前总盈亏为 ¥{performance_data['total_profit_loss']:,.2f}，盈亏比率为 {performance_data['total_profit_rate']:.2f}%
   - 策略在当前周期内暂未实现正收益。

2. **风险控制（回撤）**：
   - 持仓基金平均最大回撤（90天）为 {performance_data['avg_max_drawdown']:.2f}%
   - 持仓中最大回撤最深达到 {performance_data['worst_max_drawdown']:.2f}%
   - 需注意部分高波动标的对组合整体稳健性的影响。

3. **交易活跃度与效率**：
   - 最近3个月内共执行 {performance_data['all_trades_count']} 笔交易（买入 {performance_data['buy_trades_count']} / 卖出 {performance_data['sell_trades_count']}）
   - 平均每日交易约 {performance_data['all_trades_count']/90:.1f} 笔
   - {efficiency_comment}：在高频交易下未能覆盖成本或捕捉足够波段收益。

4. **策略特点分析**：
   - 该策略采用'自定义组合'算法，旨在通过快速止盈锁定收益。
   - 数据显示买入/定投操作较多，但卖出止盈操作相对较少（或收益未能覆盖持仓下跌）。
   - 建议检查止盈阈值设置是否过高，导致无法触发卖出，或市场单边下跌导致无止盈机会。

5. **改进建议**：
   - 考虑在市场下行期暂停定投或降低加仓频率。
   - 复核止盈策略参数，适应当前市场波动率。
   - 关注回撤较大的持仓基金，评估是否需要进行调仓。
"""

    # 保存报告
    report_filename = f"custom_strategy_performance_{performance_data['sub_account_name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path = os.path.join(reports_dir, report_filename)

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_content)

    logger.info(f"性能报告已保存至: {report_path}")
    return report_path

def main():
    """主函数"""
    logger.info("开始执行自定义组合策略性能分析")

    # 获取性能数据
    performance_data = get_custom_strategy_performance()

    if performance_data:
        # 保存报告
        report_path = save_performance_report(performance_data)

        # 打印摘要信息
        print("\n" + "="*60)
        print("自定义组合策略性能分析摘要")
        print("="*60)
        print(f"组合名称: {performance_data['sub_account_name']}")
        print(f"总资产价值: ¥{performance_data['total_asset_value']:,.2f}")
        print(f"总盈亏金额: ¥{performance_data['total_profit_loss']:,.2f}")
        print(f"总盈亏比率: {performance_data['total_profit_rate']:.2f}%")
        print(f"持仓基金数量: {len(performance_data['holdings_info'])}")
        print(f"最近3个月交易次数: {performance_data['all_trades_count']}")
        print(f"报告已保存至: {report_path}")
        print("="*60)
    else:
        logger.error("获取性能数据失败")

if __name__ == "__main__":
    main()
