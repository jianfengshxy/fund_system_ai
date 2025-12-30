import os
import sys
import json
import subprocess
import datetime
import statistics

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.db.database_connection import DatabaseConnection
from src.common.logger import get_logger

logger = get_logger("FindMatchingFunds")

def fetch_rank_data(fund_code):
    """
    Fetches historical rank data for a fund using curl command from the log file.
    """
    # Base curl command components
    url = "https://fundcomapi.tiantianfunds.com/mm/FundMNewApi/FundRankDiagram"
    
    # Construct the data string with the specific fund code
    data_param = (
        f"FCODE={fund_code}&RANGE=3y&"
        "ctoken=wNQBRXssdPQTwS7LxDmZAF_EQQB0vHyzI1uLKbciCMfQFeO3p1EDc-b-tmthy3-ygdOV2kgiLcmdZ7CT7HNPmKbZ0YPYslfNbdLlZiA0NC8VOscLHgL9g0V5Kx3834RETbSA36THb3ZdiHRpNykFIYkP4YW8dp0HCieRkC3MHjXSPVcgzvW4fwjeQy0PlfeMiUaG3fYULJ1ROGUeIa8YawqC6Fti2STUTodGi6lV2gonXoyRjnBUp2lPfkEuKTVg8pQuzUDGyDTIvyJkOx4cSw.5&"
        "deviceid=F5F9C233-F56B-4ED8-8B09-CE448DB28B3C&"
        "passportctoken=GOR9_-81zEnYmw3xp5TWD49ozr1qpULOIIwQ9yUoRIwTQem88JrRTQD0xisKLJWD7hjsCNi5Y_a00CLEK5mR8sAQzSFBwLTATG-iAPp_ZRKAixn-QKQqg_rTL5IXNyo1rWp7u17UDpd6mUPMbznWEp2iqfQpEeKGCv0XpGOkWBs&"
        "passportid=8461315737102942&"
        "passportutoken=QjaJ8B6U43EzrU9QuBKxUThD6Q31I_lmcTHRAb3hZyokq51uHNWw9TN1dAZno6qboZqs8GXv4bNKPyK461WilSX5YWLfNsy2tXjnEOExa5HSa73ozclfAQn8KFkbVp7-G2LWcdo2YK3QvyiLXPKYS7g4wnuSc6oO6-BBt_5Q2j459aePa2K2btTmMO6KXX8B0sdsrbHpXJkgLx-2ifYnpwwG3zvbNe272U470MhP_We2Hdss4puBh5HcwhJLHiRVCZqXMIyXlB7NM1vO6kikrnndm89XXvaKX6iiXb4vLT6gRBg1TSFr2Vo5XcLkVinATleOcIXeSfwadUb5k2NGRGtEdH12YVnGda3JZhQFt6Y7XPdS6ZKNMA&"
        "plat=Iphone&product=EFund&uid=cd0b7906b53b43ffa508a99744b4055b&userid=cd0b7906b53b43ffa508a99744b4055b&"
        "utoken=PXZ9SiXOeuHbJ5HoBTuAYuUSECkrJfKNReT_FD7HjAwucfw6FYopb0E_F1DxNJJ3k2lCroZWkaIN9y7Upkk0JDyQP9YetleVdB72noUIhmDmQBChnIj4r3AQlgc0ohmwjCY5TNxlueU7iMCHLYr4YU9FB1Lgbj9eHQ6mglAm7vA.5&"
        "version=6.8.3"
    )

    cmd = [
        "curl", "-s",
        "-H", "Host: fundcomapi.tiantianfunds.com",
        "-H", "tracestate: pid=0x104d5e3f0,taskid=0x174db1bc0",
        "-H", "Accept: */*",
        "-H", "GTOKEN: 03FC9273690F4DC4B71CB2247A0E4338",
        "-H", "clientInfo: ttjj-iPhone18,1-iOS-iOS26.0.1",
        "-H", "MP-VERSION: 3.6.8",
        "-H", "Accept-Language: zh-Hans-CN;q=1",
        "-H", "validmark: Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3yjfnrfzfHdSgXTLHDA0NGIiANDpxJn4QqsyZYAe8zKMA==",
        "-H", "User-Agent: EMProjJijin/6.8.3 (iPhone; iOS 26.0.1; Scale/3.00)",
        "-H", "Referer: https://mpservice.com/516939c37bdb4ba2b1138c50cf69a2e1/release/pages/increase-list/index",
        "-H", "traceparent: 00-8f41444868164c8a91be49506978b527-0000000000000000-01",
        "--data", data_param,
        "--compressed",
        url
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            logger.error(f"Curl failed for {fund_code}: {result.stderr}")
            return None
            
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON for {fund_code}: {result.stdout[:200]}")
            return None
            
    except Exception as e:
        logger.error(f"Exception during curl for {fund_code}: {e}")
        return None

def analyze_fund_trend(fund_code, fund_name):
    """
    Analyzes the trend of a fund.
    Returns (is_match, details_dict)
    """
    json_data = fetch_rank_data(fund_code)
    
    if not json_data or 'data' not in json_data or not json_data['data']:
        return False, {"error": "No data"}
    
    records = json_data['data']
    
    percentiles = []
    
    for record in records:
        try:
            rank = float(record['QRANK'])
            count = float(record['QSC'])
            if count > 0:
                percentiles.append(rank / count)
        except (ValueError, KeyError):
            continue
            
    if not percentiles:
        return False, {"error": "No valid percentiles"}
        
    # Logic from analyze_rank_trend.py
    
    # 1. Current Relative Position
    min_p = min(percentiles)
    max_p = max(percentiles)
    range_p = max_p - min_p
    current_percentile = percentiles[-1]
    
    relative_pos = (current_percentile - min_p) / range_p if range_p > 0 else 0.5
    
    # 2. Trend (Slope of last 5 points)
    recent_trend = percentiles[-5:]
    slope = 0
    if len(recent_trend) >= 2:
        slope = recent_trend[-1] - recent_trend[0]
        
    # Criteria:
    # "Approaching Worst Performance Zone": relative_pos > 0.8
    # "Performance Improvement": slope < -0.02
    
    is_match = (relative_pos > 0.8) and (slope < -0.02)
    
    return is_match, {
        "fund_code": fund_code,
        "fund_name": fund_name,
        "current_percentile": current_percentile,
        "relative_pos": relative_pos,
        "slope": slope,
        "min_p": min_p,
        "max_p": max_p
    }

def get_all_historical_funds():
    """
    Retrieves all unique fund codes and names from the database history,
    filtering for funds that appear at least 10 times.
    """
    db = DatabaseConnection()
    try:
        # Select distinct fund code and name, and count occurrences
        sql = """
            SELECT fund_code, MAX(fund_name) as fund_name, COUNT(*) as count
            FROM fund_investment_indicators 
            GROUP BY fund_code
            HAVING COUNT(*) >= 10
        """
        results = db.execute_query(sql)
        return results
    except Exception as e:
        logger.error(f"Failed to fetch funds from DB: {e}")
        return []

def main():
    print("正在从数据库获取历史加仓风向标基金(出现次数>=10)...")
    
    funds = get_all_historical_funds()
    
    if not funds:
        print("未找到任何符合条件的基金。")
        return
        
    print(f"找到 {len(funds)} 个符合条件的基金，开始分析走势...")
    print("-" * 50)
    
    matches = []
    
    for i, fund in enumerate(funds, 1):
        fund_code = fund['fund_code']
        fund_name = fund['fund_name'] or "未知名称"
        count = fund['count']
        
        print(f"[{i}/{len(funds)}] 分析 {fund_name} ({fund_code}) [出现{count}次]...", end="", flush=True)
        
        is_match, details = analyze_fund_trend(fund_code, fund_name)
        
        if is_match:
            details['occurrence_count'] = count
            print(" [符合条件!]")
            matches.append(details)
        else:
            if "error" in details:
                print(f" [跳过: {details['error']}]")
            else:
                print(f" [不符合: Pos={details['relative_pos']:.2f}, Slope={details['slope']:.3f}]")
                
    print("-" * 50)
    print(f"分析完成。共找到 {len(matches)} 个符合条件的基金：")
    
    for m in matches:
        print(f"\n基金名称: {m['fund_name']}")
        print(f"基金代码: {m['fund_code']}")
        print(f"出现次数: {m['occurrence_count']}")
        print(f"当前百分位: {m['current_percentile']*100:.1f}%")
        print(f"历史位置: {m['relative_pos']:.2f} (越接近1越差)")
        print(f"短期斜率: {m['slope']:.4f} (负数表示改善)")

    save_results_to_file(matches)

def save_results_to_file(matches):
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fund_trend_analysis_{timestamp}.txt"
    filepath = os.path.join(project_root, "logs", filename)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"分析时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"筛选条件: 历史加仓风向标出现次数 >= 10\n")
            f.write(f"共找到 {len(matches)} 个符合条件的基金：\n")
            f.write("-" * 50 + "\n")
            
            for m in matches:
                f.write(f"\n基金名称: {m['fund_name']}\n")
                f.write(f"基金代码: {m['fund_code']}\n")
                f.write(f"出现次数: {m['occurrence_count']}\n")
                f.write(f"当前百分位: {m['current_percentile']*100:.1f}%\n")
                f.write(f"历史位置: {m['relative_pos']:.2f} (越接近1越差)\n")
                f.write(f"短期斜率: {m['slope']:.4f} (负数表示改善)\n")
                f.write("-" * 30 + "\n")
                
        print(f"\n结果已保存到文件: {filepath}")
    except Exception as e:
        logger.error(f"Failed to save results to file: {e}")

if __name__ == "__main__":
    main()
