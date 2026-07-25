import logging
import requests
from typing import Dict, Any, List, Optional, Union
import os
import sys

# Add root dir to path if running as script to allow src imports
if __name__ == "__main__":
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.logger import get_logger
from src.common.requests_session import session
from src.domain.user.User import User
from src.common.constant import DEFAULT_GTOKEN, DEVICE_ID, IOS_CLIENT_INFO, IOS_USER_AGENT, MOBILE_KEY, MP_VERSION_DEFAULT, PHONE_TYPE, PLATFORM, SERVER_VERSION

logger = get_logger("FundIndexStagePerf")

def get_fund_index_stage_performance(user: User, index_code: str) -> Dict[str, Any]:
    """
    获取基金指数阶段涨幅及相关指标（上涨天数、下跌天数、胜率等）
    Args:
        user: User对象
        index_code: 市场指数代码 (e.g. "399959")
    Returns:
        Dict[str, Any]: 阶段涨幅及统计指标字典
    """
    url = "https://fundcomapi.tiantianfunds.com/mm/FundIndex/FundIndexDiy"
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-Hans-CN;q=1',
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'GTOKEN': DEFAULT_GTOKEN,
        'Host': 'fundcomapi.tiantianfunds.com',
        'MP-VERSION': MP_VERSION_DEFAULT,
        'Referer': 'https://mpservice.com/7d7b3460cd40444ba58cdabdfae34442/release/pages/index-detail/index',
        'User-Agent': IOS_USER_AGENT,
        'clientInfo': IOS_CLIENT_INFO,
        'traceparent': '00-0160dd2825e2446ba4ff1c6c6cd91ec8-0000000000000000-01',
        'tracestate': 'pid=0x105032130,taskid=0x1462b6be0',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3wGTOXNmNZFC2UPo8zBqCl4rhSrgPLj6p18fmTjJyofJQ=='
    }
    
    # ============================================================
    # 字段周期后缀统一释义:
    #   W    - Week        周
    #   M    - Month       月
    #   Q    - Quarter     季度
    #   HY   - Half Year   半年度
    #   Y    - Year        年度
    #   SY   - 近3年 (Short 3 Year)
    #   TY   - 近5年 (3-5 Year)
    #   TWY  - 近10年 (Ten Year)
    #   TRY  - 全历史区间 (Total History)
    #   FY   - 指数成立以来全部区间 (Full Year)
    #   SE   - 近3年 (Short-period Estimation, 同 SY)
    #
    # 字段分类说明:
    # ------------------------------------------------------------
    # 一、涨跌天数系列 UPDAYS / DOWNDAYS
    #     统计区间内指数收涨 / 收跌的交易日数量。
    #     用法: UPDAYS/(UPDAYS+DOWNDAYS) = 区间上涨概率(胜率)
    #
    # 二、PE/PB 百分位系列 PEP100 / PBP100
    #     市盈率/市净率在对应历史区间的百分位(0~100)。
    #     数值越低=估值低位，数值越高=估值高位。
    #
    # 三、平均涨跌幅系列 AVGSYL
    #     对应周期内指数的平均涨跌幅(收益率基准)。
    #
    # 四、上涨胜率系列 PROFIT_RATE
    #     在该周期级别下持有盈利的概率(%)
    #
    # 五、其他基础标识字段
    #     INDEXCODE, INDEXOTYPE, MAKERNAME, BASICDATE, XLFLOW_SCORE, ISUSEPBP
    # ============================================================
    fields = (
        # --- 一、涨跌天数 ---
        "UPDAYS_W,UPDAYS_M,UPDAYS_Q,UPDAYS_HY,UPDAYS_Y,"       # 近1周/1月/1季/半年/1年 上涨天数
        "UPDAYS_TWY,UPDAYS_TRY,UPDAYS_FY,UPDAYS_SY,"            # 近10年/全历史/成立以来/近3年 上涨天数
        "DOWNDAYS_W,DOWNDAYS_M,DOWNDAYS_Q,DOWNDAYS_HY,"         # 近1周/1月/1季/半年 下跌天数
        "DOWNDAYS_Y,DOWNDAYS_TWY,DOWNDAYS_TRY,DOWNDAYS_FY,"     # 近1年/近10年/全历史/成立以来 下跌天数
        "DOWNDAYS_SY,"                                           # 近3年 下跌天数
        # --- 五、基础标识 ---
        "INDEXOTYPE,ISUSEPBP,MAKERNAME,BASICDATE,BASICDATE,"     # 指数类型编码/是否优先PB估值/编制机构/基准日
        "XLFLOW_SCORE,"                                          # 资金流向综合得分(0~100)，越高资金流入越强
        # --- 四、上涨胜率 ---
        "PROFIT_RATE_TRY,PROFIT_RATE_Y,PROFIT_RATE_HY,"         # 全历史/近1年/近半年 持有胜率(%)
        "PROFIT_RATE_Q,"                                         # 近1季度 持有胜率(%)
        # --- 三、平均涨跌幅 ---
        "AVGSYL_TRY,AVGSYL_Y,AVGSYL_HY,AVGSYL_Q,"               # 全历史/近1年/近半年/近1季 平均涨跌幅(%)
        # --- 二、PE/PB 百分位 ---
        "PEP100_Y,PBP100_Y,"                                     # PE/PB 近1年百分位
        "PEP100_TRY,PBP100_TRY,"                                 # PE/PB 全历史百分位
        "PEP100_FY,PBP100_FY,"                                   # PE/PB 成立以来百分位
        "PEP100_TY,PBP100_TY,"                                   # PE/PB 近5年百分位
        "PEP100_SE,PBP100_SE"                                    # PE/PB 近3年百分位
    )
    
    # Using GET method as per curl, but passing parameters via params
    params = {
        'FCODES': index_code,
        'FIELDS': fields,
        'ctoken': user.c_token,
        'deviceid': DEVICE_ID,
        'indexTypeFields': 'TYPE_NAME,TYPE_CODE',
        'passportctoken': user.passport_ctoken or user.c_token,
        'passportid': user.passport_id,
        'passportutoken': user.passport_utoken or user.u_token,
        'plat': PLATFORM,
        'product': 'EFund',
        'uid': user.customer_no,
        'userid': user.customer_no,
        'utoken': user.u_token,
        'version': SERVER_VERSION
    }
    
    try:
        response = session.get(url, headers=headers, params=params, verify=False, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("success"):
            data_list = result.get("data", [])
            if data_list:
                return data_list[0]
            return {}
        else:
            logger.error(f"获取基金阶段涨幅失败: {result.get('message', 'Unknown error')}")
            return {}
            
    except Exception as e:
        logger.error(f"获取基金阶段涨幅异常: {e}")
        return {}

if __name__ == "__main__":
    from src.common.constant import DEFAULT_USER
    from src.API.登录接口.login import ensure_user_fresh
    
    print("Refreshing user token...")
    user = ensure_user_fresh(DEFAULT_USER)
    
    # Test with index code from example (399959 - 中证军工)
    test_index_code = "399959" 
    print(f"\n--- Testing Fund Index Stage Performance for {test_index_code} ---")
    data = get_fund_index_stage_performance(user, index_code=test_index_code)
    
    if data:
        print(f"Index Code: {data.get('INDEXCODE')}, Name: {data.get('TYPE_NAME')}")
        print(f"Up Days (Year): {data.get('UPDAYS_Y')}, Down Days (Year): {data.get('DOWNDAYS_Y')}")
        print(f"Profit Rate (Year): {data.get('PROFIT_RATE_Y')}%")
        print(f"PE Percentile (Year): {data.get('PEP100_Y')}%")
    else:
        print("Failed to get fund index stage performance.")
