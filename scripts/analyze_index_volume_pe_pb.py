"""
指数量价关系 + PE/PB 估值 + 黄金多利策略 综合分析工具

功能：
  1. 拉取指定指数的全部历史日线 K 线数据（价格、成交量、成交额）
  2. 拉取 PE-TTM / PB 10 年历史估值序列
  3. 拉取天天基金官方阶段指标（PE/PB分位、胜率、平均收益、资金热度）
  4. 六维度分析：量价关系、反转概率、回撤反弹、均线趋势、PE/PB估值、黄金多利回测
  5. 输出综合结论 + 黄金多利策略操作建议

用法：
  python scripts/analyze_index_volume_pe_pb.py              # 交互式输入指数代码
  python scripts/analyze_index_volume_pe_pb.py 399971       # 命令行指定指数代码
  python scripts/analyze_index_volume_pe_pb.py 000300       # 分析沪深300
"""

import sys
import os
import argparse
import datetime
import numpy as np
import requests
import urllib3
from collections import defaultdict

urllib3.disable_warnings()

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.API.登录接口.login import ensure_user_fresh
from src.API.市场指数.指数估值走势 import get_index_valuation_trend
from src.API.市场指数.指数阶段指标 import get_fund_index_stage_performance
from src.API.市场指数.证券日线K线行情数据 import guess_secid_from_code
from src.db.database_connection import DatabaseConnection


# ============================================================
# 0. 基金代码 → 跟踪指数解析
# ============================================================

# 已知的指数代码模式（不需要查 DB）
_INDEX_CODE_PATTERNS = frozenset(["000", "399", "930", "931", "BK", "H"])


def _is_likely_fund_code(code: str) -> bool:
    """判断输入是否更像基金代码（而非指数代码）"""
    if len(code) != 6 or not code.isdigit():
        return False
    return code[:3] in ("010", "011", "012", "013", "014", "015", "016",
                         "017", "018", "019", "050", "051", "056", "058")


def _resolve_fund_code_to_index(code: str) -> dict:
    """
    通过 market_index_static 表反向查询：基金代码 → 跟踪指数。
    返回 {"index_code": "...", "index_name": "...", "fund_code": "...", "fund_name": "..."}
    查不到返回 {}。
    """
    try:
        db = DatabaseConnection()
        rows = db.execute_query(
            "SELECT index_code, index_name, track_fund_code, track_fund_name "
            "FROM market_index_static "
            "WHERE track_fund_code = %s",
            (code,)
        )
        if rows:
            r = rows[0]
            return {
                "index_code": r["index_code"],
                "index_name": r["index_name"],
                "fund_code": r.get("track_fund_code", code),
                "fund_name": r.get("track_fund_name", ""),
            }
    except Exception as e:
        print(f"  [DB 查询异常] {e}")
    return {}


def resolve_input_code(raw_code: str) -> dict:
    """
    解析用户输入的代码，返回：
      {"index_code": "399971", "index_name": "中证传媒", "resolved_from": None}
    
    如果是基金代码（非指数模式），会自动查 DB 解析到跟踪指数。
    resolved_from 非空时表示是从基金代码解析而来。
    """
    code = raw_code.strip().upper()

    # 已知指数模式 → 直接返回
    if any(code.startswith(p) for p in _INDEX_CODE_PATTERNS):
        return {"index_code": code, "index_name": "", "resolved_from": None}

    # 可能是基金代码 → 尝试 DB 解析
    if _is_likely_fund_code(code):
        result = _resolve_fund_code_to_index(code)
        if result:
            return {
                "index_code": result["index_code"],
                "index_name": result["index_name"],
                "resolved_from": {
                    "fund_code": result["fund_code"],
                    "fund_name": result["fund_name"],
                },
            }

    # 都不匹配，原样返回（由后续 fetch 容错处理）
    return {"index_code": code, "index_name": "", "resolved_from": None}


# ============================================================
# 1. K 线数据拉取（直接 HTTP，绕过项目 session 代理）
# ============================================================

def fetch_kline_direct(index_code: str, lmt: int = 120, end: str = None):
    """直接用 requests 拉东财 push2his K 线"""
    secid = guess_secid_from_code(index_code)
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f13",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65,f66,f67",
        "klt": "101",
        "fqt": "0",
        "end": end or "20500101",
        "lmt": str(lmt),
        "ut": "a7202e6f901554f7cfadffa430c882bf",
        "authorityType": "fa",
        "dpt": "ttjj.xtb",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 26_0_1 like Mac OS X) AppleWebKit/537.36",
        "Accept": "*/*",
        "Referer": "https://mpservice.com/",
    }
    r = requests.get(url, params=params, headers=headers, timeout=30, verify=False)
    data = r.json()
    if data.get("rc") != 0 or not data.get("data"):
        return None, None, None, []
    d = data["data"]
    return d.get("name", ""), d.get("dktotal", 0), data.get("rc"), d.get("klines", [])


def fetch_all_klines(index_code: str):
    """循环拉取全部历史 K 线"""
    all_klines = []
    seen = set()
    end_date = None
    index_name = ""

    for round_idx in range(80):
        name, dktotal, rc, klines = fetch_kline_direct(index_code, lmt=120, end=end_date)
        if not klines:
            break
        if not index_name:
            index_name = name

        new_count = 0
        earliest = None
        for k in klines:
            parts = k.split(",")
            date = parts[0] if parts else ""
            if date and date not in seen:
                seen.add(date)
                all_klines.append(k)
                new_count += 1
            if earliest is None or date < earliest:
                earliest = date

        print(f"  第{round_idx+1}轮: {len(klines)}条, 新增{new_count}条, 最早={earliest}")

        if new_count == 0 or not earliest:
            break
        dt = datetime.datetime.strptime(earliest, "%Y-%m-%d")
        end_date = (dt - datetime.timedelta(days=1)).strftime("%Y%m%d")

    if not all_klines:
        print(f"\n❌ 未能获取 {index_code} 的 K 线数据（secid={guess_secid_from_code(index_code)}）。")
        print("   可能原因：该指数代码不被东财 push2his 接口支持，或 secid 推断有误。")
        print("   提示：可尝试使用深交所指数（399xxx）或上交所指数（000xxx 除跨市场外）。")
        return index_name, []

    all_klines.sort(key=lambda k: k.split(",")[0])
    print(f"\n共获取 {len(all_klines)} 条, 日期范围: {all_klines[0].split(',')[0]} ~ {all_klines[-1].split(',')[0]}")
    return index_name, all_klines


def parse_kline(kline_str: str) -> dict:
    """解析单条 K 线: date,open,close,high,low,volume,amount,amplitude,chg_pct,chg,turnover"""
    parts = kline_str.split(",")

    def f(i):
        if i < 0 or i >= len(parts): return None
        try: return float(parts[i])
        except: return None

    def fi(i):
        if i < 0 or i >= len(parts): return None
        try: return int(float(parts[i]))
        except: return None

    return {
        "date": parts[0] if parts else "",
        "open": f(1), "close": f(2), "high": f(3), "low": f(4),
        "volume": fi(5), "amount": f(6),
        "amplitude": f(7), "chg_pct": f(8), "chg": f(9), "turnover": f(10),
    }


# ============================================================
# 2. 分析函数
# ============================================================

def volume_analysis(klines_parsed):
    """量价关系"""
    print("\n" + "=" * 70)
    print("【一、量价关系分析】")
    print("=" * 70)

    n = len(klines_parsed)
    vol_ratio_bins = {"放量上涨": 0, "放量下跌": 0, "缩量上涨": 0, "缩量下跌": 0}
    vol_next = {"放量": {"涨": 0, "跌": 0}, "缩量": {"涨": 0, "跌": 0}}
    vol_ratios = []

    for i in range(1, n - 1):
        prev_vol = klines_parsed[i - 1]["volume"] or 0
        curr_vol = klines_parsed[i]["volume"] or 0
        curr_chg = klines_parsed[i]["chg_pct"] or 0
        next_chg = klines_parsed[i + 1]["chg_pct"] or 0

        if prev_vol <= 0: continue
        vr = curr_vol / prev_vol
        vol_ratios.append(vr)

        is_vol_up = vr >= 1.1
        is_price_up = curr_chg >= 0

        if is_vol_up and is_price_up: vol_ratio_bins["放量上涨"] += 1
        elif is_vol_up and not is_price_up: vol_ratio_bins["放量下跌"] += 1
        elif not is_vol_up and is_price_up: vol_ratio_bins["缩量上涨"] += 1
        else: vol_ratio_bins["缩量下跌"] += 1

        if is_vol_up:
            vol_next["放量"]["涨" if next_chg > 0 else "跌"] += 1
        else:
            vol_next["缩量"]["涨" if next_chg > 0 else "跌"] += 1

    total = sum(vol_ratio_bins.values())
    print(f"\n样本量: {total} 天")
    for k, v in vol_ratio_bins.items():
        print(f"  {k}: {v}天 ({v / total * 100:.1f}%)")

    for vt in ["放量", "缩量"]:
        up = vol_next[vt]["涨"]; down = vol_next[vt]["跌"]
        tp = up + down
        if tp > 0:
            print(f"  {vt}次日: 涨概率={up / tp * 100:.1f}% ({up}/{tp})  |  跌概率={down / tp * 100:.1f}%")

    # 极端成交量
    if vol_ratios:
        vr_arr = np.array(vol_ratios)
        p80 = np.percentile(vr_arr, 80)
        p20 = np.percentile(vr_arr, 20)

        for label, cond in [("极端放量(>P80)", lambda v: v >= p80), ("极端缩量(<P20)", lambda v: v <= p20)]:
            next_chgs = []
            for i in range(1, n - 1):
                pv = klines_parsed[i - 1]["volume"] or 0
                cv = klines_parsed[i]["volume"] or 0
                if pv > 0 and cond(cv / pv):
                    next_chgs.append(klines_parsed[i + 1]["chg_pct"] or 0)
            if next_chgs:
                avg = np.mean(next_chgs)
                win = sum(1 for x in next_chgs if x > 0) / len(next_chgs) * 100
                print(f"  {label}次日: 平均涨跌={avg:+.2f}%, 上涨概率={win:.1f}%, 样本={len(next_chgs)}")


def price_pattern_analysis(klines_parsed):
    """价格形态分析"""
    print("\n" + "=" * 70)
    print("【二、连续涨跌后反转概率】")
    print("=" * 70)

    n = len(klines_parsed)
    for days in [3, 5, 7]:
        rebound = []
        for i in range(days, n - 1):
            if all((klines_parsed[i - j]["chg_pct"] or 0) < 0 for j in range(days, 0, -1)):
                rebound.append(klines_parsed[i + 1]["chg_pct"] or 0)
        if rebound:
            win = sum(1 for x in rebound if x > 0) / len(rebound) * 100
            print(f"  连跌{days}天后次日: 平均={np.mean(rebound):+.2f}%, 反弹概率={win:.1f}%, 样本={len(rebound)}")

        pullback = []
        for i in range(days, n - 1):
            if all((klines_parsed[i - j]["chg_pct"] or 0) > 0 for j in range(days, 0, -1)):
                pullback.append(klines_parsed[i + 1]["chg_pct"] or 0)
        if pullback:
            win = sum(1 for x in pullback if x > 0) / len(pullback) * 100
            print(f"  连涨{days}天后次日: 平均={np.mean(pullback):+.2f}%, 继续涨概率={win:.1f}%, 样本={len(pullback)}")


def drawdown_analysis(klines_parsed):
    """回撤与反弹"""
    print("\n" + "=" * 70)
    print("【三、阶段回撤后反弹力度】")
    print("=" * 70)

    closes = [k["close"] for k in klines_parsed if k["close"] is not None]
    n = len(closes)

    for window in [60, 120]:
        results = defaultdict(list)
        for i in range(window, n):
            wh = max(closes[i - window:i + 1])
            dd = (closes[i] - wh) / wh * 100

            if dd <= -20: key = "回撤>20%"
            elif dd <= -15: key = "回撤15-20%"
            elif dd <= -10: key = "回撤10-15%"
            elif dd <= -5: key = "回撤5-10%"
            else: key = "回撤<5%"

            for fo, lb in [(21, "1月"), (63, "3月"), (126, "6月")]:
                if i + fo < n:
                    fc = (closes[i + fo] - closes[i]) / closes[i] * 100
                    results[(key, lb)].append(fc)

        print(f"\n  滚动{window}日高点回撤:")
        for key in ["回撤>20%", "回撤15-20%", "回撤10-15%", "回撤5-10%", "回撤<5%"]:
            for lb in ["1月", "3月", "6月"]:
                vals = results.get((key, lb), [])
                if vals:
                    win = sum(1 for v in vals if v > 0) / len(vals) * 100
                    print(f"    {key} → 未来{lb}: 平均={np.mean(vals):+.2f}%, 胜率={win:.1f}%, 样本={len(vals)}")


def trend_analysis(klines_parsed):
    """趋势与均线"""
    print("\n" + "=" * 70)
    print("【四、均线趋势分析】")
    print("=" * 70)

    closes = np.array([k["close"] for k in klines_parsed if k["close"] is not None])
    current = closes[-1]

    for ma in [20, 60, 120, 250]:
        if len(closes) < ma: continue
        ma_val = np.mean(closes[-ma:])
        dev = (current - ma_val) / ma_val * 100
        ma5_trend = (ma_val - np.mean(closes[-ma - 5:-ma])) / np.mean(closes[-ma - 5:-ma]) * 100 if len(closes) >= ma + 5 else 0
        direction = "↑ 向上" if ma5_trend > 0.1 else ("↓ 向下" if ma5_trend < -0.1 else "→ 走平")
        print(f"  MA{ma:>3}: {ma_val:.2f}  当前价={current:.2f}  偏离={dev:+.2f}%  趋势={direction}")

    # 多空排列
    ma20 = np.mean(closes[-20:]) if len(closes) >= 20 else 0
    ma60 = np.mean(closes[-60:]) if len(closes) >= 60 else 0
    ma120 = np.mean(closes[-120:]) if len(closes) >= 120 else 0
    ma250 = np.mean(closes[-250:]) if len(closes) >= 250 else 0
    if ma20 and ma60 and ma120 and ma250:
        bullish = current > ma20 > ma60 > ma120 > ma250
        bearish = current < ma20 < ma60 < ma120 < ma250
        if bullish:   print(f"\n  → 多头排列（价格 > MA20 > MA60 > MA120 > MA250）")
        elif bearish: print(f"\n  → 空头排列（价格 < MA20 < MA60 < MA120 < MA250）")
        else:         print(f"\n  → 均线交织，方向待确认")


def pe_pb_analysis(klines_parsed, pe_dict, pb_dict):
    """PE/PB 估值分析"""
    print("\n" + "=" * 70)
    print("【五、PE/PB 估值与未来收益率】")
    print("=" * 70)

    k_by_date = {k["date"]: k for k in klines_parsed if k["close"] is not None}
    all_dates = sorted(set(list(pe_dict.keys()) + list(pb_dict.keys())))

    matched = []
    for i, d in enumerate(all_dates):
        pe = pe_dict.get(d); pb = pb_dict.get(d)
        k = k_by_date.get(d)
        if k is None: continue
        close = k["close"]
        fwd = {}
        for fo, lb in [(21, "1m"), (63, "3m"), (126, "6m"), (252, "12m")]:
            best = None
            for j in range(i + 1, min(i + fo + 15, len(all_dates))):
                fk = k_by_date.get(all_dates[j])
                if fk and j - i >= fo * 0.7:
                    best = (fk["close"] - close) / close * 100
                    break
            fwd[lb] = best
        matched.append({"d": d, "close": close, "pe": pe, "pb": pb, "fwd": fwd})

    print(f"匹配 {len(matched)} 个数据点")

    def _print_groups(vals_arr, label_prefix, getter):
        if vals_arr.size == 0: return
        p25, p50, p75 = np.percentile(vals_arr, [25, 50, 75])
        print(f"\n{label_prefix} 分位: P25={p25:.2f}, P50={p50:.2f}, P75={p75:.2f}")

        groups = [
            (f"{label_prefix}低位(<P25)", lambda m: getter(m) is not None and getter(m) <= p25),
            (f"{label_prefix}中低(P25-P50)", lambda m: getter(m) is not None and p25 < getter(m) <= p50),
            (f"{label_prefix}中高(P50-P75)", lambda m: getter(m) is not None and p50 < getter(m) <= p75),
            (f"{label_prefix}高位(>P75)", lambda m: getter(m) is not None and getter(m) > p75),
        ]
        for label, cond in groups:
            g = [m for m in matched if cond(m)]
            if g:
                print(f"\n  {label} ({len(g)}天):")
                for lb in ["1m", "3m", "6m", "12m"]:
                    vals = [m["fwd"].get(lb) for m in g if m["fwd"].get(lb) is not None]
                    if vals:
                        win = sum(1 for v in vals if v > 0) / len(vals) * 100
                        print(f"    未来{lb}: 平均={np.mean(vals):+.2f}%, 胜率={win:.1f}%")

    pe_vals = np.array([m["pe"] for m in matched if m["pe"] is not None])
    _print_groups(pe_vals, "PE-TTM", lambda m: m["pe"])

    pb_vals = np.array([m["pb"] for m in matched if m["pb"] is not None])
    _print_groups(pb_vals, "PB", lambda m: m["pb"])

    # 当前位置
    cur_pe = next((m["pe"] for m in reversed(matched) if m["pe"]), None)
    cur_pb = next((m["pb"] for m in reversed(matched) if m["pb"]), None)
    if cur_pe and pe_vals.size > 0:
        pct = sum(1 for v in pe_vals if v <= cur_pe) / len(pe_vals) * 100
        print(f"\n>>> 当前 PE-TTM = {cur_pe:.2f}, 处于 {pct:.1f}% 历史分位")
    if cur_pb and pb_vals.size > 0:
        pct = sum(1 for v in pb_vals if v <= cur_pb) / len(pb_vals) * 100
        print(f">>> 当前 PB = {cur_pb:.2f}, 处于 {pct:.1f}% 历史分位")

    return matched


def gold_strategy_backtest(klines_parsed, pe_dict):
    """黄金多利策略回测"""
    print("\n" + "=" * 70)
    print("【六、黄金多利策略-历史回测】")
    print("=" * 70)

    closes = np.array([k["close"] for k in klines_parsed if k["close"] is not None])
    dates = [k["date"] for k in klines_parsed if k["close"] is not None]
    n = len(closes)

    BUY_THRESHOLD = -1.0
    BUY_TWICE = -4.0
    STOP_SKIP = -5.0
    BASE_AMT = 2000
    INITIAL_CASH = 100000

    returns_arr = np.diff(closes) / closes[:-1] * 100
    rolling_vol = [5.0] * 250
    for i in range(20, len(returns_arr)):
        rolling_vol.append(np.std(returns_arr[i - 20:i]) * np.sqrt(252))

    pe_vals_for_dates = [pe_dict.get(d) for d in dates]

    cash = INITIAL_CASH
    shares = 0
    cost_total = 0
    trades = []

    init_buy = INITIAL_CASH * 0.2
    init_price = closes[250]
    shares = init_buy / init_price
    cost_total = init_buy
    cash -= init_buy
    trades.append((dates[250], "初始建仓", init_buy, 0.0))

    for i in range(251, n):
        price = closes[i]
        pos_val = shares * price
        profit_pct = (pos_val - cost_total) / cost_total * 100 if cost_total > 0 else 0
        vol = rolling_vol[i] if i < len(rolling_vol) else 5.0
        stop_rate = min(max(vol, 5.0), 15.0)

        if profit_pct > stop_rate or profit_pct > 10.0:
            sell_shares = shares * 0.5
            sell_amount = sell_shares * price
            cash += sell_amount
            shares -= sell_shares
            cost_total = cost_total * (shares / (shares + sell_shares)) if shares + sell_shares > 0 else 0
            trades.append((dates[i], "止盈50%", sell_amount, profit_pct))
            continue

        today_chg = (klines_parsed[i]["chg_pct"] or 0) if i < len(klines_parsed) else 0
        est_profit = profit_pct + today_chg

        if est_profit < BUY_THRESHOLD and est_profit > STOP_SKIP:
            mult = 2.0 if est_profit < BUY_TWICE else 1.0
            buy_amount = BASE_AMT * mult

            pe_now = pe_vals_for_dates[i] if i < len(pe_vals_for_dates) else None
            if pe_now is not None:
                pe_arr = np.array([v for v in pe_vals_for_dates[:i + 1] if v is not None])
                if pe_arr.size > 100:
                    pe_pct = sum(1 for v in pe_arr if v <= pe_now) / len(pe_arr) * 100
                    if pe_pct < 30:
                        buy_amount *= 1.5

            if buy_amount > cash:
                buy_amount = cash
            if buy_amount < 100:
                continue

            new_shares = buy_amount / price
            cash -= buy_amount
            shares += new_shares
            cost_total += buy_amount
            trades.append((dates[i], f"加仓x{mult:.0f}", buy_amount, profit_pct))

    final_val = shares * closes[-1] + cash
    total_ret = (final_val - INITIAL_CASH) / INITIAL_CASH * 100
    print(f"\n初始现金={INITIAL_CASH:,.0f}  最终持仓={shares * closes[-1]:,.0f}  现金={cash:,.0f}")
    print(f"总资产={final_val:,.0f}  策略收益={total_ret:+.2f}%")
    print(f"交易次数={len(trades)}  加仓={sum(1 for t in trades if '加仓' in t[1])}  止盈={sum(1 for t in trades if t[1] == '止盈50%')}")

    buy_hold_ret = (closes[-1] - closes[250]) / closes[250] * 100
    print(f"同期买入持有收益: {buy_hold_ret:+.2f}%")

    if trades:
        print(f"\n最近10笔交易:")
        for t in trades[-10:]:
            print(f"  {t[0]} | {t[1]} | {t[2]:,.0f} | 收益率={t[3]:.2f}%")


# ============================================================
# 3. 主流程
# ============================================================

def _valuation_pct_label(vals_arr, current_val) -> tuple:
    """计算当前值的历史分位，返回 (分位%, 标签)"""
    if vals_arr.size == 0 or current_val is None:
        return 0, "无数据"
    pct = sum(1 for v in vals_arr if v <= current_val) / len(vals_arr) * 100
    if pct < 20:   label = "极度低估"
    elif pct < 40: label = "低估"
    elif pct < 60: label = "合理"
    elif pct < 80: label = "偏高"
    else:          label = "高估"
    return pct, label


def main():
    parser = argparse.ArgumentParser(
        description="指数量价关系 + PE/PB 估值 + 黄金多利策略综合分析"
    )
    parser.add_argument("input_code", nargs="?", default=None,
                        help="指数或基金代码（如 399971、012769），不传则交互式输入")
    args = parser.parse_args()

    # 获取输入代码
    raw_code = args.input_code
    if not raw_code:
        raw_code = input("请输入指数/基金代码（如 399971 或 012769）: ").strip()
    if not raw_code:
        print("未输入代码，退出。")
        sys.exit(1)

    # 解析代码：如果是基金代码，自动查 DB 找到跟踪指数
    resolved = resolve_input_code(raw_code)
    index_code = resolved["index_code"]

    if resolved["resolved_from"]:
        rf = resolved["resolved_from"]
        print(f"\n📎 识别为基金代码 {rf['fund_code']}（{rf['fund_name']}）")
        print(f"   → 自动解析到跟踪指数: {index_code}（{resolved['index_name']}）")

    print("=" * 70)
    print(f" {index_code} 量价+PE/PB+黄金多利 综合分析")
    print("=" * 70)

    # 拉取 K 线数据
    print("\n>> 拉取K线数据...")
    index_name_from_kline, all_klines = fetch_all_klines(index_code)
    if not all_klines:
        sys.exit(1)
    # 优先使用 DB 预解析的名称，其次用 K 线接口返回的名称
    index_name = resolved.get("index_name") or index_name_from_kline
    klines_parsed = [parse_kline(k) for k in all_klines]
    print(f">> 指数名称: {index_name}")
    print(f">> 解析 {len(klines_parsed)} 条有效K线")

    # 登录并拉估值
    print("\n>> 登录并拉取PE/PB估值数据...")
    user = ensure_user_fresh(DEFAULT_USER)

    pe_dict, pb_dict = {}, {}
    for vt, label in [("PETTM", "PE"), ("PB", "PB")]:
        print(f"  拉取{label} 10年数据...")
        resp = get_index_valuation_trend(user, index_code, index_value_type=vt, range_param="10n")
        if resp.success:
            for p in resp.items:
                if vt == "PETTM": pe_dict[p.PDATE] = p.PETTM
                else:             pb_dict[p.PDATE] = p.PB
            print(f"    {label}: {len(resp.items)} 条, expansion={resp.expansion}")
        else:
            print(f"    {label}: 失败 - {resp.first_error}")

    print("\n>> 拉取阶段指标...")
    stage = get_fund_index_stage_performance(user, index_code)

    # ============================================================
    # 执行分析
    # ============================================================
    volume_analysis(klines_parsed)
    price_pattern_analysis(klines_parsed)
    drawdown_analysis(klines_parsed)
    trend_analysis(klines_parsed)
    pe_pb_analysis(klines_parsed, pe_dict, pb_dict)
    gold_strategy_backtest(klines_parsed, pe_dict)

    # ============================================================
    # 综合结论
    # ============================================================
    print("\n" + "=" * 70)
    print("【综合结论 & 策略应用】")
    print("=" * 70)

    closes = np.array([k["close"] for k in klines_parsed if k["close"] is not None])
    current_price = closes[-1]
    chg_1m = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) > 21 else 0
    chg_3m = (closes[-1] - closes[-63]) / closes[-63] * 100 if len(closes) > 63 else 0
    chg_6m = (closes[-1] - closes[-126]) / closes[-126] * 100 if len(closes) > 126 else 0

    last60 = closes[-61:]
    rets = np.diff(last60) / last60[:-1] * 100
    recent_vol = np.std(rets) * np.sqrt(252)

    print(f"\n  📊 当前状态:")
    print(f"     指数名称: {index_name}({index_code})")
    print(f"     最新收盘: {current_price:.2f}")
    print(f"     近1月涨跌: {chg_1m:+.2f}%")
    print(f"     近3月涨跌: {chg_3m:+.2f}%")
    print(f"     近6月涨跌: {chg_6m:+.2f}%")
    print(f"     年化波动率: {recent_vol:.2f}%")

    # PE/PB
    pe_vals_arr = np.array(list(pe_dict.values()))
    pb_vals_arr = np.array(list(pb_dict.values()))
    latest_pe = max(pe_dict.items())[1] if pe_dict else None
    latest_pb = max(pb_dict.items())[1] if pb_dict else None

    if latest_pe and pe_vals_arr.size > 0:
        pct, label = _valuation_pct_label(pe_vals_arr, latest_pe)
        print(f"     PE-TTM: {latest_pe:.2f} → {label} (历史 {pct:.1f}% 分位)")

    if latest_pb and pb_vals_arr.size > 0:
        pct, label = _valuation_pct_label(pb_vals_arr, latest_pb)
        print(f"     PB: {latest_pb:.2f} → {label} (历史 {pct:.1f}% 分位)")

    if stage:
        print(f"     资金热度: {stage.get('XLFLOW_SCORE', '')}/100")
        print(f"     近1年PE分位: {stage.get('PEP100_Y', '')}%  近3年: {stage.get('PEP100_TRY', '')}%  近5年: {stage.get('PEP100_FY', '')}%")
        print(f"     近1年胜率: {stage.get('PROFIT_RATE_Y', '')}%  |  近3年胜率: {stage.get('PROFIT_RATE_TRY', '')}%")
        print(f"     近1年平均收益: {stage.get('AVGSYL_Y', '')}%  |  近3年: {stage.get('AVGSYL_TRY', '')}%")

    # 黄金多利策略建议
    print(f"\n  🎯 黄金多利策略 - 操作建议:")
    print(f"     策略规则: 加仓=预估收益率<-1% | 双倍加仓=<-4% | 跳过=<-5% | 止盈=收益率>max(波动率,5%) | 强制止盈=>10%")

    if chg_1m < -1.0:
        if chg_1m > -5.0:
            m = 2 if chg_1m < -4.0 else 1
            print(f"     ✅ 触发加仓: 近1月跌幅 {chg_1m:.2f}% < -1%, 建议 {m} 倍加仓 (基础金额 2000)")
            if latest_pe and pe_vals_arr.size > 0 and sum(1 for v in pe_vals_arr if v <= latest_pe) / len(pe_vals_arr) * 100 < 30:
                print(f"     💡 PE低位，可选择额外加码 1.5x")
        else:
            print(f"     ⚠️  近1月跌幅 {chg_1m:.2f}% < -5%, 暂停加仓等待企稳")
    elif chg_1m > (min(max(recent_vol, 5.0), 15.0)):
        print(f"     🚀 触发止盈: 近1月涨幅 {chg_1m:.2f}% > 止盈点 {min(max(recent_vol, 5.0), 15.0):.1f}%, 建议卖出0费率份额")
    else:
        print(f"     ⏸️  持有: 近1月涨跌 {chg_1m:.2f}% 在策略区间内")

    # 走势预判
    print(f"\n  🔮 未来最大概率走势判断:")
    if latest_pe and pe_vals_arr.size > 0:
        pe_pct, _ = _valuation_pct_label(pe_vals_arr, latest_pe)
        if pe_pct < 30:
            print(f"     PE处于历史{pe_pct:.1f}%低分位，历史数据显示此估值区间买入:")
            print(f"     → 未来半年胜率较高，适合逐步加仓布局")
            print(f"     → 建议使用黄金多利策略，PE低位可适当加大加仓倍率")
        elif pe_pct < 50:
            print(f"     PE处于历史{pe_pct:.1f}%中低分位，估值合理偏低:")
            print(f"     → 正常执行黄金多利策略，保持标准加仓/止盈节奏")
        elif pe_pct < 70:
            print(f"     PE处于历史{pe_pct:.1f}%中高分位，估值偏高:")
            print(f"     → 谨慎加仓，可适当降低加仓倍率或提高止盈阈值")
        else:
            print(f"     PE处于历史{pe_pct:.1f}%高分位，估值偏贵:")
            print(f"     → 建议以止盈为主，减少加仓频率")

    print("\n" + "=" * 70)
    print("分析完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
