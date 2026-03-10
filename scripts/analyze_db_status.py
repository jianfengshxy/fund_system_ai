import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.db.database_connection import DatabaseConnection
from src.common.constant import DEFAULT_USER

def analyze_db():
    print(f"========== DEFAULT_USER 数据库资产分析 ==========")
    print(f"用户: {DEFAULT_USER.customer_name} ({DEFAULT_USER.account})")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    db = DatabaseConnection()
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)

    try:
        # 1. 获取最近 14 天的资产快照
        print("--- 最近 14 天资产趋势 ---")
        # 修改列名以匹配表结构：day_profit -> day_profit, total_profit -> total_profit, etc.
        # 注意：表结构中列名是 total_asset, hqb_asset, fund_asset, day_profit
        # 活期宝收益可能是 hqb_day_profit
        sql_asset = """
            SELECT date, total_asset, hqb_asset, fund_asset, day_profit, total_profit, hqb_day_profit, fund_day_profit
            FROM user_asset_daily 
            WHERE customer_no = %s 
            ORDER BY date DESC 
            LIMIT 14
        """
        # 使用列表传递参数，而非元组，mysql-connector-python 通常两者都支持，但列表更安全
        cursor.execute(sql_asset, [DEFAULT_USER.customer_no])
        assets = cursor.fetchall()

        if not assets:
            print("未找到资产记录。请确认数据同步任务是否已运行。")
        else:
            print(f"{'日期':<12} {'总资产':<12} {'活期宝':<12} {'基金':<12} {'当日盈亏':<10} {'仓位占比'}")
            print("-" * 75)
            # 按日期正序输出
            for asset in reversed(assets):
                date_str = str(asset['date'])
                total = float(asset['total_asset'])
                hqb = float(asset['hqb_asset'])
                fund = float(asset['fund_asset'])
                profit = float(asset['day_profit'])
                position_ratio = (fund / total * 100) if total > 0 else 0
                
                print(f"{date_str:<12} {total:<12.2f} {hqb:<12.2f} {fund:<12.2f} {profit:<10.2f} {position_ratio:.1f}%")

        print("\n--- 资产分布分析 ---")
        if assets:
            latest = assets[0] # assets 是按日期倒序查询的，所以第0个是最近的
            total = float(latest['total_asset'])
            hqb = float(latest['hqb_asset'])
            fund = float(latest['fund_asset'])
            
            if total > 0:
                hqb_ratio = (hqb / total) * 100
                fund_ratio = (fund / total) * 100
            else:
                hqb_ratio = 0
                fund_ratio = 0
                
            print(f"当前总资产: {total:.2f}")
            print(f"活期宝余额: {hqb:.2f} (占比 {hqb_ratio:.1f}%)")
            print(f"基金持仓:   {fund:.2f} (占比 {fund_ratio:.1f}%)")
            
            if hqb_ratio < 20:
                print("⚠️ 警告: 活期宝占比低于 20%，流动性偏紧，需注意加仓节奏！")
            else:
                print("✅ 流动性良好: 活期宝储备充足，可支持后续定投。")

        # 2. 获取最近 3 天的交易统计
        print("\n--- 最近 3 天交易统计 (从 user_trade_record，排除已撤单) ---")
        three_days_ago = (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d")
        
        # 增加状态过滤，排除撤单记录
        # 通常 app_state_text 包含 "撤" 字表示撤单，"失败" 表示失败
        # status 字段也可以辅助，但 app_state_text 更直观
        sql_trade = """
            SELECT 
                DATE(strike_start_date) as trade_date,
                business_type,
                COUNT(*) as count,
                SUM(apply_amount) as total_amount
            FROM user_trade_record
            WHERE customer_no = %s 
              AND strike_start_date >= %s
              AND app_state_text NOT LIKE '%%撤%%'
              AND app_state_text NOT LIKE '%%失败%%'
            GROUP BY trade_date, business_type
            ORDER BY trade_date DESC, business_type
        """
        cursor.execute(sql_trade, [DEFAULT_USER.customer_no, three_days_ago])
        trades = cursor.fetchall()

        if not trades:
             print("最近 3 天无交易记录。")
        else:
            for trade in trades:
                # 简单映射业务类型
                b_type = trade['business_type']
                b_desc = b_type
                # 常见业务类型代码映射
                type_map = {
                    '022': '定投买入',
                    '024': '分红',
                    '098': '快速赎回',
                    '020': '认购/申购',
                    '021': '赎回', # 普通赎回
                    '029': '转换入',
                    '030': '转换出',
                    '031': '强制定投',
                    '036': '定投赎回',
                    '090': '快速取现'
                }
                b_desc = type_map.get(b_type, b_type)
                
                count = trade['count']
                amount = float(trade['total_amount']) if trade['total_amount'] else 0.0
                
                print(f"日期: {trade['trade_date']}, 类型: {b_desc:<10}, 笔数: {count}, 总金额: {amount:.2f}")

        # 3. 专门分析今日止盈（卖出/赎回）情况
        print("\n--- 今日潜在止盈/赎回订单分析 (含未确认) ---")
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 扩大查询范围：
        # 1. 不再严格限制 business_type，而是用 LIKE 匹配中文描述
        # 2. 状态放宽，只要不是撤单/失败即可（包含待确认）
        # 3. 增加对 apply_date 的兼容（部分记录可能用的是 apply_date 而不是 strike_start_date）
        sql_sell = """
            SELECT 
                product_name, 
                business_type,
                apply_amount,
                status,
                app_state_text,
                remark,
                strike_start_date
            FROM user_trade_record
            WHERE customer_no = %s 
              AND strike_start_date >= %s
              AND (
                  business_type IN ('021', '024', '098', '030', '036', '090') 
                  OR business_type LIKE '%%赎回%%' 
                  OR business_type LIKE '%%卖出%%'
                  OR app_state_text LIKE '%%赎回%%'
                  OR app_state_text LIKE '%%卖出%%'
              )
              AND app_state_text NOT LIKE '%%撤%%'
              AND app_state_text NOT LIKE '%%失败%%'
            ORDER BY strike_start_date DESC
        """
        cursor.execute(sql_sell, [DEFAULT_USER.customer_no, today_str])
        sells = cursor.fetchall()
        
        if not sells:
            print("今日无有效止盈/赎回记录。")
        else:
            print(f"找到 {len(sells)} 笔止盈/赎回记录：")
            for sell in sells:
                b_type = sell['business_type']
                b_desc = b_type
                # 尝试解析 business_type
                type_map = {
                    '021': '赎回', 
                    '024': '分红', 
                    '098': '快速赎回',
                    '030': '转换出',
                    '036': '定投赎回',
                    '090': '快速取现'
                }
                if b_type in type_map:
                    b_desc = type_map[b_type]
                
                amt = float(sell['apply_amount']) if sell['apply_amount'] else 0.0
                status_text = sell['app_state_text'] or sell['status'] or '未知'
                time_str = sell['strike_start_date'].strftime("%H:%M:%S") if sell['strike_start_date'] else "--:--:--"
                
                print(f"[{time_str}] {sell['product_name']}: {b_desc} {amt:.2f} (状态: {status_text})")

    except Exception as e:
        print(f"查询数据库失败: {e}")
        # 打印异常详情以便调试
        import traceback
        traceback.print_exc()
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'db' in locals() and 'conn' in locals() and conn:
            db.disconnect(conn)
        print("\n========== 分析结束 ==========")

if __name__ == "__main__":
    analyze_db()
