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
    "上银", "兴银", "加银", "兴证资管", "汇安", "中航",
    
    # 市场/类型/形式
    "中证", "国证", "上证", "深证", "创业板", "科创板", "港股通", "沪港深", "标普", "纳斯达克", "恒生",
    "指数", "ETF", "联接", "发起式", "发起", "LOF", "QDII", "FOF", "REITs",
    
    # 泛指修饰
    "主题", "产业", "行业", "细分", "龙头", "精选", "优选", "配置", "混合", "股票",
    "增强", "策略", "量化", "价值", "成长", "回报", "稳健", "灵活", "优势", "动力",
    "机遇", "创新", "驱动", "先锋", "领先", "核心", "主要", "金麒麟", "兴享", "优择", "领航", "智选", "睿恒",
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

def getAllThemes(user, page_size=200) -> ApiResponse[List[str]]:
    """
    获取所有去重后的主题列表
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为200，尽可能获取更多数据以覆盖更多主题
    
    返回:
    ApiResponse: 包含去重后主题列表的响应对象
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
    
    logger = logging.getLogger("ThemeListAPI")
    
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
        themes = set()
        
        for item in data_list:
            fund_name = item.get('SHORTNAME', '')
            # 过滤掉A类基金（名称以A或a结尾）
            if fund_name and fund_name.upper().endswith('A'):
                continue
                
            # 1. 尝试从指数名称获取主题
            sec_info = item.get('SEC_INFO', {})
            index_name = sec_info.get('INDEXNAME', '')
            if index_name:
                themes.add(index_name)
            else:
                # 2. 如果没有指数名称，尝试从基金名称提取核心主题
                core_name = get_core_name(fund_name)
                if core_name:
                    themes.add(core_name)
            
        return ApiResponse(
            Success=True,
            ErrorCode=None,
            Data=list(themes),
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
        print("正在获取所有主题列表...")
        # 测试API接口
        result = getAllThemes(DEFAULT_USER, page_size=200)
        
        if result.Success:
            print("\n=== API调用成功 ===")
            print(f"成功状态: {result.Success}")
            print(f"获取到的主题数量: {len(result.Data) if result.Data else 0}")
            print("===================================")
            
            if result.Data:
                # 排序输出
                sorted_themes = sorted(result.Data)
                print("主题列表:")
                for i, theme in enumerate(sorted_themes, 1):
                    print(f"{i}. {theme}")
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
