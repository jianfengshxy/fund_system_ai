#!/usr/bin/env python3
import sys
import os
import requests
import argparse

# 项目根目录
ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger
from src.domain.fund.fund_info import FundInfo
from src.common.constant import DEFAULT_USER
from src.common.constant import SERVER_VERSION, PHONE_TYPE, MOBILE_KEY, DEVICE_ID

logger = get_logger("Script")

def fetch_high_freq_codes(db: DatabaseConnection, days: int = 100, min_times: int = 10):
    sql = (
        "SELECT fund_code, MAX(fund_name) AS fund_name, COUNT(*) AS cnt "
        "FROM fund_investment_indicators "
        "WHERE update_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY) "
        "GROUP BY fund_code HAVING cnt > %s ORDER BY cnt DESC"
    )
    return db.execute_query(sql, (days, min_times))

def compute_drawdown_percent(user, fund_code: str, nav_window: int = 100) -> float:
    url = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNHisNetList'
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundmobapi.eastmoney.com',
        'Accept': '*/*',
        'GTOKEN': '4474AFD3E15F441E937647556C01C174',
        'clientInfo': 'ttjj-iPhone12,3-iOS-iOS15.5',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZd9JYBOfWXLz4ujEjOUCkzX5OOMubE0Xuw+PGl6/XhtW6uCaNvvGARgUd92574Ft++7hwQ65WREqAHqpIQXfammA==',
        'User-Agent': 'EMProjJijin/6.5.5 (iPhone; iOS 15.5; Scale/3.00)',
        'Referer': 'https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/fundHistoryWorth/index',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    data = {
        'FCODE': fund_code,
        'IsShareNet': 'true',
        'MobileKey': MOBILE_KEY,
        'OSVersion': '15.5',
        'appType': 'ttjj',
        'appVersion': SERVER_VERSION,
        'cToken': user.c_token,
        'deviceid': DEVICE_ID,
        'pageIndex': '0',
        'pageSize': str(nav_window),
        'passportid': user.passport_id,
        'plat': PHONE_TYPE,
        'product': 'EFund',
        'serverVersion': SERVER_VERSION,
        'uToken': user.u_token,
        'userId': user.customer_no,
        'version': SERVER_VERSION
    }
    try:
        r = requests.post(url, headers=headers, data=data, verify=False, timeout=10)
        r.raise_for_status()
        jd = r.json()
        datas = jd.get('Datas') or []
        if not datas:
            return 0.0
        navs = []
        for d in datas:
            v = d.get('DWJZ')
            if v is None or v == '--' or v == '':
                continue
            try:
                navs.append(float(v))
            except Exception:
                pass
        if not navs:
            return 0.0
        curr = navs[0]
        peak = max(navs)
        if peak <= 0:
            return 0.0
        dd = (peak - curr) / peak * 100.0
        return dd
    except Exception:
        return 0.0

def main():
    parser = argparse.ArgumentParser(description="筛选高频出现且高回撤的基金")
    parser.add_argument("--days", type=int, default=50, help="考察最近多少个交易日 (默认: 50)")
    parser.add_argument("--min-times", type=int, default=10, help="最小出现次数 (默认: 10)")
    parser.add_argument("--dd", type=float, default=0.0, help="最小回撤百分比阈值 (默认: 0.0)")
    parser.add_argument("--window", type=int, default=100, help="计算回撤的净值窗口大小 (默认: 100)")
    args = parser.parse_args()

    print(f"筛选条件: 最近 {args.days} 天出现 > {args.min_times} 次 (窗口: {args.window}天)")
    if args.dd > 0:
        print(f"过滤条件: 回撤 > {args.dd}%")

    db = DatabaseConnection()
    rows = fetch_high_freq_codes(db, days=args.days, min_times=args.min_times)
    if not rows:
        print("未找到满足出现次数条件的基金")
        return
    user = DEFAULT_USER
    results = []
    for r in rows:
        code = r['fund_code']
        name = r.get('fund_name') or code
        cnt = r['cnt']
        dd_pct = compute_drawdown_percent(user, code, nav_window=args.window)
        if dd_pct >= args.dd:
            results.append({'code': code, 'name': name, 'cnt': cnt, 'dd': dd_pct})

    if not results:
        print(f"没有基金同时满足条件")
        return

    # 按照回撤幅度大小排序(回撤越大越在前面)
    results.sort(key=lambda x: x['dd'], reverse=True)

    print("\n符合条件的基金（按回撤幅度排序）：")
    
    # 辅助函数：计算字符串显示宽度（中文2，英文1）
    def get_display_width(s):
        w = 0
        for char in s:
            if '\u4e00' <= char <= '\u9fff' or '\uff00' <= char <= '\uffef':
                w += 2
            else:
                w += 1
        return w

    # 辅助函数：填充字符串到指定显示宽度
    def pad_str(s, width):
        curr_w = get_display_width(s)
        padding = max(0, width - curr_w)
        return s + ' ' * padding

    header_rank = pad_str("排名", 6)
    header_name = pad_str("基金名称", 40)
    header_code = pad_str("代码", 10)
    header_dd = pad_str("回撤%", 10)
    header_cnt = pad_str("出现次数", 8)
    
    print(f"{header_rank}{header_name}{header_code}{header_dd}{header_cnt}")
    print("-" * 80)
    
    for i, item in enumerate(results, 1):
        name = item['name']
        # 简单截断防止过长（保留前20个汉字左右）
        if len(name) > 20:
             cname = name[:19] + '…'
        else:
             cname = name
             
        p_rank = pad_str(str(i), 6)
        p_name = pad_str(cname, 40)
        p_code = pad_str(item['code'], 10)
        p_dd = pad_str(f"{item['dd']:.2f}", 10)
        p_cnt = pad_str(str(item['cnt']), 8)
        
        print(f"{p_rank}{p_name}{p_code}{p_dd}{p_cnt}")

if __name__ == '__main__':
    main()
