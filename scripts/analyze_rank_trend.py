import json
import datetime
import statistics

def find_peaks_valleys(data, distance=5):
    """
    Simple peak/valley detection.
    Returns indices of peaks and valleys.
    """
    peaks = []
    valleys = []
    
    if len(data) < 3:
        return peaks, valleys

    # Simple local extrema detection
    # We look for points that are higher/lower than neighbors within 'distance'
    for i in range(len(data)):
        start = max(0, i - distance)
        end = min(len(data), i + distance + 1)
        window = data[start:end]
        
        # Check for peak (local max)
        if data[i] == max(window) and data[i] != min(window): # Avoid flat lines
            # Check if it's strictly greater than immediate neighbors to avoid plateaus logic complication
            # For simplicity, we just take the first occurrence in a window if multiple equal maxes exist? 
            # Let's keep it simple: if it's the max of the window
            # To avoid duplicate peaks for the same event (e.g. 1, 2, 5, 5, 2), we can just check immediate neighbors
            if i > 0 and i < len(data) - 1:
                if data[i] > data[i-1] and data[i] > data[i+1]:
                     peaks.append(i)
        
        # Check for valley (local min)
        if data[i] == min(window) and data[i] != max(window):
             if i > 0 and i < len(data) - 1:
                if data[i] < data[i-1] and data[i] < data[i+1]:
                    valleys.append(i)
                    
    return peaks, valleys

def analyze_trend(file_path):
    # Read the file content
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return

    # Find the JSON part
    try:
        json_start = content.find('{')
        if json_start == -1:
            print("Could not find JSON start")
            return
        json_content = content[json_start:]
        data = json.loads(json_content)
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return

    if 'data' not in data:
        print("No data found in JSON")
        return

    records = data['data']
    
    # Process data
    dates = []
    ranks = []
    total_counts = []
    percentiles = []

    print(f"总记录数: {len(records)}")

    for record in records:
        date_str = record['PDATE']
        rank = float(record['QRANK'])
        count = float(record['QSC'])
        
        dates.append(datetime.datetime.strptime(date_str, "%Y-%m-%d"))
        ranks.append(rank)
        total_counts.append(count)
        # Percentile: Rank/Count
        # Low percentile = Good performance (Top)
        # High percentile = Bad performance (Bottom)
        percentiles.append(rank / count)

    # Smooth the data (Simple Moving Average)
    window_size = 3
    smoothed_percentiles = []
    valid_dates = []
    
    for i in range(len(percentiles) - window_size + 1):
        window = percentiles[i:i+window_size]
        avg = sum(window) / window_size
        smoothed_percentiles.append(avg)
        # Associate with the middle date or end date? Let's say end date of window
        valid_dates.append(dates[i + window_size - 1])

    # Find peaks and valleys
    # High Percentile = Peak = Bad Performance
    # Low Percentile = Valley = Good Performance
    peaks_idx, valleys_idx = find_peaks_valleys(smoothed_percentiles, distance=3)

    print("\n--- 分析报告 ---")
    
    peak_dates = [valid_dates[i] for i in peaks_idx]
    valley_dates = [valid_dates[i] for i in valleys_idx]
    
    print(f"\n识别出 {len(peaks_idx)} 个业绩'低谷'（排名靠后，百分比峰值）于：")
    for d in peak_dates:
        print(f"  {d.strftime('%Y-%m-%d')}")
        
    print(f"\n识别出 {len(valleys_idx)} 个业绩'顶峰'（排名靠前，百分比谷值）于：")
    for d in valley_dates:
        print(f"  {d.strftime('%Y-%m-%d')}")

    cycle_durations = []
    
    # Calculate cycle based on Peaks (Bottom-to-Bottom)
    if len(peak_dates) > 1:
        for i in range(len(peak_dates)-1):
            days = (peak_dates[i+1] - peak_dates[i]).days
            cycle_durations.append(days)
            
    # Calculate cycle based on Valleys (Top-to-Top)
    if len(valley_dates) > 1:
        for i in range(len(valley_dates)-1):
            days = (valley_dates[i+1] - valley_dates[i]).days
            cycle_durations.append(days)
        
    if cycle_durations:
        avg_cycle = statistics.mean(cycle_durations)
        print(f"\n预估波动周期: {avg_cycle:.1f} 天")
    else:
        print("\n数据点不足以预估周期。")

    # Current Position Analysis
    current_date = dates[-1]
    current_percentile = percentiles[-1]
    current_rank = ranks[-1]
    
    print(f"\n当前状态 ({current_date.strftime('%Y-%m-%d')}):")
    print(f"  排名: {current_rank:.0f} / {total_counts[-1]:.0f}")
    print(f"  百分位: {current_percentile*100:.1f}% (越低越好)")
    
    # Determine trend (last 5 days)
    recent_trend = percentiles[-5:]
    if len(recent_trend) >= 2:
        slope = recent_trend[-1] - recent_trend[0]
        if slope > 0.02:
            trend_str = "业绩下滑 (排名数值增加)"
        elif slope < -0.02:
            trend_str = "业绩改善 (排名数值减少)"
        else:
            trend_str = "稳定"
    else:
        trend_str = "未知"
        
    print(f"  短期趋势: {trend_str}")
    
    # Determine relative position
    min_p = min(percentiles)
    max_p = max(percentiles)
    range_p = max_p - min_p
    
    relative_pos = (current_percentile - min_p) / range_p if range_p > 0 else 0.5
    
    if relative_pos < 0.2:
        pos_desc = "接近最佳业绩区 (高水位)"
    elif relative_pos > 0.8:
        pos_desc = "接近最差业绩区 (低水位)"
    else:
        # Check direction relative to smoothed curve
        # If we are falling from a peak?
        pos_desc = f"中游水平 (距离最佳 {relative_pos*100:.0f}%)"
        
    print(f"  近期历史相对位置: {pos_desc}")

if __name__ == "__main__":
    file_path = "/Users/m672372/Documents/fund_system_ai/logs/近3个月同类排名走势图.txt"
    analyze_trend(file_path)
