import logging
import requests
import json
import re
from typing import List, Dict, Any, Optional

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER
from src.common.requests_session import session
from src.domain.fund_plan import ApiResponse
from src.domain.fund.fund_info import FundInfo

# 噪音词列表，用于提取基金核心主题
NOISE_WORDS = [
    # 基金公司
    "易方达", "汇添富", "海富通", "工银瑞信", "交银施罗德", "东方红", "泰达宏利", "申万菱信",
    "博时", "平安", "永赢", "南方", "嘉实", "华夏", "富国", "广发", "鹏华", "工银", 
    "招商", "天弘", "华安", "银华", "国泰", "大成", "华宝", "中欧", "交银", "建信",
    "光大", "中银", "民生", "信诚", "国投", "瑞银", "农银", "汇丰", "华泰", "新华",
    "申万", "菱信", "泰达", "宏利", "摩根", "上投", "浦银", "安信", "万家", "景顺", "长城",
    "融通", "诺安", "长信", "宝盈", "前海", "开源", "金鹰", "银河", "中金", "中信", "东吴",
    "财通", "信达", "方正", "英大", "红土", "浙商", "国金", "西部", "北信", "创金", "中邮",
    "长安", "东兴", "华融", "国开", "中融", "九泰", "红塔", "华宸", "格林", "恒生", "惠升",
    "同泰", "南华", "淳厚", "博道", "合煦", "恒越", "蜂巢", "达诚", "明亚", "博远", "朱雀",
    "同济", "瑞达", "凯石", "湘财", "国融", "易米", "兴华", "尚正", "汇泉", "百嘉", "兴合",
    "泉果", "汇百", "国新", "国能", "苏新", "华商", "泓德", "中加", "国寿", "安邦", "太平",
    "人保", "泰康", "大家", "华富", "贝莱德", "富达", "路博迈", "施罗德", "联博",
    "上银", "兴银", "加银",
    
    # 市场/类型/形式
    "中证", "国证", "上证", "深证", "创业板", "科创板", "港股通", "沪港深", "标普", "纳斯达克", "恒生",
    "指数", "ETF", "联接", "发起式", "发起", "LOF", "QDII", "FOF", "REITs",
    
    # 泛指修饰
    "主题", "产业", "行业", "细分", "龙头", "精选", "优选", "配置", "混合", "股票",
    "增强", "策略", "量化", "价值", "成长", "回报", "稳健", "灵活", "优势", "动力",
    "机遇", "创新", "驱动", "先锋", "领先", "核心", "主要", 
    "持有", "滚动", "定开", "一年", "三年", "两年", "六个月", "三个月", "一周", "双周",
    "短债", "中短债", "中债", "信用", "纯债", "可转债", "转债", "货币", "理财",
    
    # 字母后缀
    "A", "B", "C", "D", "E", "H", "I"
]

def get_core_name(name: str) -> str:
    """提取基金核心名称（主题）"""
    # 1. 去除括号及内容
    name = re.sub(r'\(.*?\)', '', name)
    name = re.sub(r'（.*?）', '', name)
    
    # 2. 去除末尾的字母 (C, A 等)
    name = re.sub(r'[A-Z]+$', '', name)
    
    # 3. 迭代去除噪音词
    temp_name = name
    for word in NOISE_WORDS:
        temp_name = temp_name.replace(word, "")
    
    # 4. 去除数字
    temp_name = re.sub(r'\d+', '', temp_name)
    
    # 5. 如果剩不下什么了，返回原名（避免过滤过度）
    if not temp_name.strip():
        return name
        
    return temp_name.strip()

def filter_duplicate_funds(funds: List[FundInfo]) -> List[FundInfo]:
    """过滤重复主题的基金，只保留排名靠前的"""
    unique_funds = []
    seen_cores = []
    seen_types = set()
    
    for fund in funds:
        # 1. 优先检查 API 返回的主题类型 (fund_type)
        if fund.fund_type and fund.fund_type != '未知':
            if fund.fund_type in seen_types:
                continue # 跳过重复主题
            seen_types.add(fund.fund_type)
            unique_funds.append(fund)
            # 同时也把核心名加入 seen_cores，以防万一
            core_name = get_core_name(fund.fund_name)
            seen_cores.append(core_name)
            continue

        # 2. 如果没有 API 主题，回退到基于名称的核心词去重
        core_name = get_core_name(fund.fund_name)
        
        # 检查是否重复
        is_duplicate = False
        for seen in seen_cores:
            # 相互包含即视为重复（保留先出现的那个，即涨幅高的）
            if core_name in seen or seen in core_name:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_funds.append(fund)
            seen_cores.append(core_name)
            
    return unique_funds

def getThemeSelectedFunds(user, page_size=10) -> ApiResponse[List[FundInfo]]:
    """
    获取主题选择基金信息
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为10
    
    返回:
    ApiResponse: 包含主题选择基金信息列表的响应对象
    """
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundTheme/FundThemeSelectFund'
    
    headers = {
        "Host": "fundcomapi.tiantianfunds.com",
        "Accept": "*/*",
        "GTOKEN": "03FC9273690F4DC4B71CB2247A0E4338",
        "clientInfo": "ttjj-iPhone18,1-iOS-iOS26.0.1",
        "MP-VERSION": "2.12.0",
        "tracestate": "pid=0x1050b0820,taskid=0x1699195c0",
        "Accept-Language": "zh-Hans-CN;q=1",
        "User-Agent": "EMProjJijin/6.8.3 (iPhone; iOS 26.0.1; Scale/3.00)",
        "Referer": "https://mpservice.com/fund26a41652d42d4d/release/pages/home-sub-page",
        "traceparent": "00-3533964c7d85407988810aa51bc55d55-0000000000000000-01"
    }
    
    params = {
        "FIELDS": "SEC_CODE,FTYPE,FCODE,SHORTNAME,Y,SE,LJJZ,BFUNDTYPE,YRANK,YCOUNT",
        "MobileKey": "F5F9C233-F56B-4ED8-8B09-CE448DB28B3C",
        "RELATETYPE": "",
        "TFIELDS": "Y,SEC_CODE,INDEXNAME,INDEXCODE",
        "ctoken": user.c_token,
        "deviceId": "F5F9C233-F56B-4ED8-8B09-CE448DB28B3C",
        "deviceid": "F5F9C233-F56B-4ED8-8B09-CE448DB28B3C",
        "gtoken": "03FC9273690F4DC4B71CB2247A0E4338",
        "pageIndex": "1",
        "pageSize": str(page_size),
        "passportId": user.passport_id,
        "passportctoken": user.passport_ctoken,
        "passportid": user.passport_id,
        "passportutoken": user.passport_utoken,
        "plat": "Iphone",
        "platid": "1",
        "product": "EFund",
        "serverversion": "6.8.3",
        "sort": "desc",
        "sortColumn": "Y",
        "userId": user.customer_no,
        "userid": user.customer_no,
        "utoken": user.u_token
    }
    
    logger = logging.getLogger("ThemeSelectedFundsAPI")
    
    try:
        # 使用域名而不是IP，并设置verify=False
        response = session.get(url, params=params, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        
        if not json_data.get('success', False):
             return ApiResponse(
                Success=json_data.get('success', False),
                ErrorCode=json_data.get('errorCode'),
                Data=None,
                FirstError=json_data.get('firstError'),
                DebugError=json_data.get('hasWrongToken')
            )

        data_list = json_data.get('data', [])
        indicators = []
        
        for item in data_list:
            # 映射API字段到FundInfo所需的字段
            # API: FCODE, SHORTNAME, Y (收益?), YRANK (排名)
            # FundInfo: FCODE, SHORTNAME
            
            fund_name = item.get('SHORTNAME', '')
            # 过滤掉A类基金（名称以A或a结尾）
            if fund_name and fund_name.upper().endswith('A'):
                continue
                
            sec_info = item.get('SEC_INFO', {})
            index_name = sec_info.get('INDEXNAME', '')
            
            fund_data = {
                'FCODE': item.get('FCODE'),
                'SHORTNAME': fund_name,
                # 这里暂时将Y映射到今年来收益率，虽然可能不准确，但作为一个参考值
                'SYL_JN': item.get('Y'), 
                'GSZ': 0.0, # 未知
                'GSZZL': 0.0, # 未知
                'ISBUY': '1', # 默认为可买
                'RSFUNDTYPE': index_name if index_name else '未知', # 使用指数名称作为类型
                'NAV': 0.0,
                'ACCNAV': 0.0,
                'PDATE': '',
                'NAVCHGRT': 0.0
            }
            
            fund_info = FundInfo.from_dict(fund_data)
            # 可以在这里额外保存一些信息，例如 YRANK
            # fund_info.rank_info = item.get('YRANK') 
            
            indicators.append(fund_info)
            
        # 过滤重复主题的基金
        indicators = filter_duplicate_funds(indicators)
            
        return ApiResponse(
            Success=True,
            ErrorCode=None,
            Data=indicators,
            FirstError=None,
            DebugError=None
        )
        
    except requests.exceptions.RequestException as e:
        logger.error(f'API请求失败: {str(e)}')
        return ApiResponse(
            Success=False,
            ErrorCode='REQUEST_ERROR',
            Data=None,
            FirstError=f'请求失败: {str(e)}',
            DebugError=None
        )
    except Exception as e:
        logger.error(f'API调用异常: {str(e)}')
        return ApiResponse(
            Success=False,
            ErrorCode='UNKNOWN_ERROR',
            Data=None,
            FirstError=f'未知错误: {str(e)}',
            DebugError=None
        )

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 禁用 urllib3 警告
    urllib3_logger = logging.getLogger('urllib3')
    urllib3_logger.setLevel(logging.CRITICAL)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        print("正在获取主题选择基金信息...")
        # 测试API接口
        result = getThemeSelectedFunds(DEFAULT_USER, page_size=50)
        
        if result.Success:
            print("\n=== API调用成功 ===")
            print(f"成功状态: {result.Success}")
            print(f"数据条数: {len(result.Data) if result.Data else 0}")
            print("===================================")
            
            if result.Data:
                for i, info in enumerate(result.Data, 1):
                    print(f"{i}. {info.fund_name} ({info.fund_code})")
                    print(f"   主题/类型: {info.fund_type}")
                    print(f"   相关指标(Y): {info.this_year_return}")
                    print("-----------------------------------")
            else:
                print("无数据")
        else:
            print("\n=== API调用失败 ===")
            print(f"错误代码: {result.ErrorCode}")
            print(f"错误信息: {result.FirstError}")
            if result.DebugError:
                print(f"调试错误: {result.DebugError}")
    except Exception as e:
        print("\n=== 执行过程中发生异常 ===")
        print(f"异常信息: {str(e)}")
