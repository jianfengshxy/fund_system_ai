#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指数 3 个月高胜率条件扫描器
=============================
对 AI 预测报告中的所有指数，回测历史数据，找出 P(3个月涨幅 > 20%) >= 65% 的估值条件，
并检查当前是否满足。满足的排在前面，不满足的按接近程度排序。

用法:
    python3 scripts/scan_3m_high_prob.py

输出:
    - 终端表格：满足条件的指数（绿色✅）+ 不满足的（按差距排序）
    - 可选输出到 CSV
"""

import sys, os, re, argparse
from datetime import datetime
from typing import Optional, List, Dict, Tuple

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

from service.市场指数.market_index_service import MarketIndexService
from service.AI预测.index_predictor import IndexPredictor

# ---------- 配置 ----------
TARGET_RETURN = 20.0       # 目标涨幅阈值 (%)
MIN_PROB = 0.65            # 最低概率要求
MIN_SAMPLES = 5            # 条件最少历史样本数
MIN_HISTORY_DAYS = 120     # 指数最少需要的历史数据条数

# ---------- 特征名 ----------
FN = ["pe_pct","pb_pct","heat_score","pe_ttm","pb",
      "ret_5d","ret_10d","ret_20d","ret_60d",
      "ma20_dev","ma60_dev","vol_20d","pe_pct_chg_60d"]


def parse_report_indices(report_path: str) -> List[Tuple[str, str]]:
    """从 AI 预测报告中提取所有指数代码和名称，保持报告原始排序。"""
    with open(report_path, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r'^### \d+\. \[\w+\] (\S+) (.+)$', re.MULTILINE)
    return [(m.group(1), m.group(2)) for m in pattern.finditer(content)]


def find_threshold(data: List[Tuple], feature_idx: int, is_lower_better: bool = True) -> Optional[Dict]:
    """
    对单个特征做阈值扫描，找到最低 P(3M > TARGET_RETURN) >= MIN_PROB 的阈值。
    
    data: [(date, feature_vector, y3m_return), ...]
    
    Returns:
        {
            'threshold': float,       # 达标阈值
            'prob': float,            # 实际概率
            'avg_ret': float,         # 平均收益
            'count': int,             # 样本数
        }
        或 None（不满足 MIN_SAMPLES 或达不到 MIN_PROB）
    """
    best = None
    
    # 尝试的阈值列表
    if is_lower_better:
        thresholds = list(range(5, 60, 5))  # 5,10,15,...,55
    else:
        thresholds = list(range(5, 60, 5))
    
    for th in thresholds:
        if is_lower_better:
            matches = [(d, f, r) for d, f, r in data if f[feature_idx] < th]
        else:
            matches = [(d, f, r) for d, f, r in data if f[feature_idx] > th]
        
        if len(matches) < MIN_SAMPLES:
            continue
        
        gt_target = sum(1 for _, _, r in matches if r > TARGET_RETURN)
        prob = gt_target / len(matches)
        
        if prob >= MIN_PROB:
            avg_ret = sum(r for _, _, r in matches) / len(matches)
            best = {
                'threshold': th,
                'prob': round(prob, 4),
                'avg_ret': round(avg_ret, 2),
                'count': len(matches),
            }
            break  # 第一个满足的就是最宽松的阈值
    
    return best


def evaluate_index(svc: MarketIndexService,
                   index_code: str, index_name: str) -> Optional[Dict]:
    """
    评估单个指数：获取数据 → 扫描阈值 → 检查当前是否达标。
    
    Returns:
        dict 或 None（数据不足）
    """
    # 1. 获取历史数据
    records = svc.get_index_history(index_code)
    if not records or len(records) < MIN_HISTORY_DAYS:
        return None
    
    # 2. 构建特征（使用静态方法，避免创建额外的 Predictor 实例 / DB 连接）
    X, y1m, y3m, y6m, dates = IndexPredictor._build_features(records)
    if len(X) < MIN_SAMPLES:
        return None
    
    # 3. 收集有效 (特征, 3个月标签) 对
    valid_data = [(dates[i], X[i], y3m[i]) for i in range(len(X)) if y3m[i] is not None]
    if len(valid_data) < MIN_SAMPLES:
        return None
    
    # 4. 当前特征值
    current_fv = X[-1]
    cur_date = str(dates[-1]) if dates else "N/A"
    
    # 实际可用的 3个月标签数量
    actual_3m = sum(1 for i in range(len(X)) if y3m[i] is not None)
    
    # 5. 扫描 PE分位 和 PB分位 的达标阈值
    pe_idx = FN.index("pe_pct")
    pb_idx = FN.index("pb_pct")
    
    pe_th = find_threshold(valid_data, pe_idx, is_lower_better=True)
    pb_th = find_threshold(valid_data, pb_idx, is_lower_better=True)
    
    # 当前值
    cur_pe = round(float(current_fv[pe_idx]), 2)
    cur_pb = round(float(current_fv[pb_idx]), 2)
    
    # 6. 判断是否满足
    pe_ok = pe_th is not None and cur_pe < pe_th['threshold']
    pb_ok = pb_th is not None and cur_pb < pb_th['threshold']
    
    is_satisfied = pe_ok or pb_ok
    
    # 7. 构建结果
    result = {
        'code': index_code,
        'name': index_name,
        'date': cur_date,
        'data_days': len(records),
        'valid_samples': actual_3m,
        'cur_pe': cur_pe,
        'cur_pb': cur_pb,
        'is_satisfied': is_satisfied,
        'pe_ok': pe_ok,
        'pb_ok': pb_ok,
        'pe_threshold': pe_th,
        'pb_threshold': pb_th,
    }
    
    # 8. 计算排序用的分数
    if is_satisfied:
        # 满足的：按 (PE达标概率 + PB达标概率) 取最大值排序
        pe_p = pe_th['prob'] if pe_ok and pe_th else 0
        pb_p = pb_th['prob'] if pb_ok and pb_th else 0
        result['sort_score'] = max(pe_p, pb_p)
        result['best_prob'] = result['sort_score']
        result['best_condition'] = ('PE' if pe_p >= pb_p else 'PB') if max(pe_p, pb_p) > 0 else 'N/A'
    else:
        # 不满足的：计算与达标阈值的"接近度"
        closeness = 0.0
        missing_info = []
        
        if pe_th:
            # 需要 cur_pe < threshold, gap = cur_pe - threshold（正值表示差多少）
            gap = cur_pe - pe_th['threshold']
            if gap <= 0:
                closeness = max(closeness, 1.0)  # PE条件已满足（但PB或其他条件未满足）
            else:
                # 越接近阈值，分数越高
                c = max(0, 1.0 - gap / max(pe_th['threshold'], 1))
                closeness = max(closeness, c)
                missing_info.append(f"PE需从{cur_pe:.1f}%降至<{pe_th['threshold']}%（差{gap:.1f}pp，达标概率{pe_th['prob']:.0%}）")
        
        if pb_th:
            # 需要 cur_pb < threshold
            gap = cur_pb - pb_th['threshold']
            if gap <= 0:
                closeness = max(closeness, 1.0)
            else:
                c = max(0, 1.0 - gap / max(pb_th['threshold'], 1))
                closeness = max(closeness, c)
                missing_info.append(f"PB需从{cur_pb:.1f}%降至<{pb_th['threshold']}%（差{gap:.1f}pp，达标概率{pb_th['prob']:.0%}）")
        
        if not pe_th and not pb_th:
            missing_info.append("历史数据中无任何条件能达到65%胜率")
        
        result['sort_score'] = closeness
        result['missing_info'] = missing_info
        result['best_prob'] = pe_th['prob'] if pe_th else (pb_th['prob'] if pb_th else 0)
        result['best_condition'] = 'N/A'
    
    return result


def format_table(results: List[Dict]) -> str:
    """生成终端表格输出。"""
    lines = []
    sep = "=" * 130
    
    lines.append(sep)
    lines.append(f"  指数 3 个月高胜率条件扫描  |  目标: 涨幅 > {TARGET_RETURN}% 概率 >= {MIN_PROB:.0%}  |  扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(sep)
    lines.append("")
    
    satisfied = [r for r in results if r['is_satisfied']]
    unsatisfied = [r for r in results if not r['is_satisfied']]
    
    # ===== 满足条件的 =====
    lines.append(f"  ✅ 已满足条件: {len(satisfied)} 个指数")
    lines.append(f"  {'─'*125}")
    
    if satisfied:
        hdr = f"  {'排名':<4} {'代码':<12} {'名称':<20} {'满足条件':<8} {'胜率':>6} {'均值':>8} {'当前PE%':>8} {'当前PB%':>8} {'要求':<20}"
        lines.append(hdr)
        lines.append(f"  {'─'*125}")
        
        for i, r in enumerate(satisfied, 1):
            cond = r['best_condition']
            prob = r['best_prob']
            
            if cond == 'PE' and r['pe_threshold']:
                req = f"PE < {r['pe_threshold']['threshold']}%"
                avg = r['pe_threshold']['avg_ret']
            elif cond == 'PB' and r['pb_threshold']:
                req = f"PB < {r['pb_threshold']['threshold']}%"
                avg = r['pb_threshold']['avg_ret']
            else:
                req = "N/A"
                avg = 0
            
            lines.append(
                f"  {i:<4} {r['code']:<12} {r['name']:<20} {cond:<8} {prob:>5.1%} {avg:>+8.2f}% "
                f"{r['cur_pe']:>8.1f} {r['cur_pb']:>8.1f} {req:<20}"
            )
    
    lines.append("")
    
    # ===== 不满足条件的 =====
    lines.append(f"  ❌ 未满足条件: {len(unsatisfied)} 个指数（按接近程度排序）")
    lines.append(f"  {'─'*125}")
    
    if unsatisfied:
        hdr = f"  {'排名':<4} {'代码':<12} {'名称':<20} {'接近度':>6} {'当前PE%':>8} {'当前PB%':>8} {'差距/所需条件'}"
        lines.append(hdr)
        lines.append(f"  {'─'*125}")
        
        for i, r in enumerate(unsatisfied, 1):
            closeness = r['sort_score']
            missing = r.get('missing_info', ['N/A'])
            
            # 第一行：基本信息和第一个缺失条件
            first_missing = missing[0] if missing else 'N/A'
            lines.append(
                f"  {i:<4} {r['code']:<12} {r['name']:<20} {closeness:>5.1%} "
                f"{r['cur_pe']:>8.1f} {r['cur_pb']:>8.1f} {first_missing}"
            )
            
            # 额外的缺失条件
            if len(missing) > 1:
                for extra in missing[1:]:
                    lines.append(f"  {'':>47}{extra}")
    
    lines.append("")
    lines.append(sep)
    lines.append(f"  合计: {len(satisfied)} 达标 / {len(unsatisfied)} 未达标 / {len(results)} 总计")
    lines.append(sep)
    
    return "\n".join(lines)


def export_csv(results: List[Dict], output_path: str):
    """导出 CSV。"""
    import csv
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['状态', '代码', '名称', '数据日期', '当前PE分位', '当前PB分位',
                     'PE达标阈值', 'PE实际胜率', 'PB达标阈值', 'PB实际胜率',
                     '接近度', '差距描述'])
        for r in results:
            status = '达标' if r['is_satisfied'] else '未达标'
            pe_th_val = r['pe_threshold']['threshold'] if r['pe_threshold'] else ''
            pe_th_prob = f"{r['pe_threshold']['prob']:.1%}" if r['pe_threshold'] else ''
            pb_th_val = r['pb_threshold']['threshold'] if r['pb_threshold'] else ''
            pb_th_prob = f"{r['pb_threshold']['prob']:.1%}" if r['pb_threshold'] else ''
            missing = '; '.join(r.get('missing_info', []))
            
            w.writerow([
                status, r['code'], r['name'], r['date'],
                f"{r['cur_pe']:.1f}%", f"{r['cur_pb']:.1f}%",
                pe_th_val, pe_th_prob, pb_th_val, pb_th_prob,
                f"{r['sort_score']:.2%}", missing,
            ])
    print(f"\n  CSV 已导出: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="指数 3 个月高胜率条件扫描器")
    parser.add_argument("--report", default=None,
                        help="AI 预测报告路径，默认自动找最新的")
    parser.add_argument("--csv", default=None,
                        help="导出 CSV 路径")
    parser.add_argument("--top", type=int, default=0,
                        help="只显示前 N 个（0=全部）")
    args = parser.parse_args()
    
    # 报告路径
    if args.report:
        report_path = args.report
    else:
        reports_dir = os.path.join(ROOT, "reports")
        reports = sorted(
            [f for f in os.listdir(reports_dir) if f.startswith("AI预测报告_") and f.endswith(".md")],
            reverse=True
        )
        if not reports:
            print("错误: 未找到报告文件")
            sys.exit(1)
        report_path = os.path.join(reports_dir, reports[0])
    
    print(f"读取报告: {report_path}")
    
    # 解析指数
    indices = parse_report_indices(report_path)
    print(f"报告覆盖指数: {len(indices)} 个")
    
    # 初始化服务（只用1个 DB 连接）
    svc = MarketIndexService()
    
    # 逐指数评估
    results = []
    skipped = 0
    for idx, (code, name) in enumerate(indices):
        if (idx + 1) % 50 == 0:
            print(f"  进度: {idx+1}/{len(indices)} ...")
        
        r = evaluate_index(svc, code, name)
        if r is None:
            skipped += 1
            continue
        results.append(r)
    
    # 排序: 满足的在前（按概率降序），不满足的在後（按接近度降序）
    satisfied = [r for r in results if r['is_satisfied']]
    unsatisfied = [r for r in results if not r['is_satisfied']]
    
    satisfied.sort(key=lambda x: x['sort_score'], reverse=True)
    unsatisfied.sort(key=lambda x: x['sort_score'], reverse=True)
    
    sorted_results = satisfied + unsatisfied
    
    # 截取
    if args.top > 0:
        sorted_results = sorted_results[:args.top]
    
    # 输出
    table = format_table(sorted_results)
    print(table)
    
    if skipped > 0:
        print(f"\n  跳过 {skipped} 个指数（历史数据不足 {MIN_HISTORY_DAYS} 条）")
    
    # CSV 导出
    if args.csv:
        export_csv(sorted_results, args.csv)


if __name__ == "__main__":
    main()
