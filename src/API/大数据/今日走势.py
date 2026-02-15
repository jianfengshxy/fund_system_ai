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

from src.common.constant import DEFAULT_USER, SERVER_VERSION, PHONE_TYPE
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

def getBatchFundDetails(user, fund_codes: List[str]) -> Dict[str, FundInfo]:
    """
    批量获取基金详细信息
    """
    if not fund_codes:
        return {}
        
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundFavor/FundFavorInfo'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': 'fundcomapi.tiantianfunds.com',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'forceLog': '1',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '32',
        'traceparent': '00-0000000046aa4cae00000196718a8166-0000000000000000-01',
        'tracestate': 'pid=0x6f96620,taskid=0xabc5123',
        'Content-Type': 'application/x-www-form-urlencoded',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1DXqiIOSu/kLYsAt37vKDFhzWESfp9O5+28eHlMZFdAOKtOr630iFFehhF8ZZ2O0=',
        'Referer': 'https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/all-list/index'
    }
    
    logger = logging.getLogger("FundBatchDetails")
    result_map = {}
    
    # 分批处理，每次最多查询 50 个
    batch_size = 50
    for i in range(0, len(fund_codes), batch_size):
        batch_codes = fund_codes[i:i+batch_size]
        codes_str = ','.join(batch_codes)
        
        data = {
            'FIELDS': 'MAXSG,FCODE,SHORTNAME,PDATE,NAV,ACCNAV,NAVCHGRT,NAVCHGRT100,GSZ,GSZZL,GZTIME,NEWPRICE,CHANGERATIO,ZJL,HQDATE,ISREDBAGS,SYL_Z,SYL_Y,SYL_3Y,SYL_6Y,SYL_JN,SYL_1N,SYL_2N,SYL_3N,SYL_5N,SYL_LN,RSBTYPE,RSFUNDTYPE,INDEXCODE,NEWINDEXTEXCH,TRKERROR1,ISBUY',
            'product': 'EFund',
            'APPID': 'FAVOR,FAVOR_ED,FAVOR_GS',
            'pageSize': 200,
            'passportctoken': user.passport_ctoken,
            'SortColumn': '',
            'passportutoken': user.passport_utoken,
            'deviceid': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
            'userid': user.customer_no,
            'version': SERVER_VERSION,
            'ctoken': user.c_token,
            'uid': user.customer_no,
            'CODES': codes_str,
            'pageIndex': 1,
            'utoken': user.u_token,
            'Sort': '',
            'plat': PHONE_TYPE,
            'passportid': user.passport_id
        }
        
        try:
            response = session.post(url, data=data, headers=headers, verify=False, timeout=10)
            response.raise_for_status()
            json_data = response.json()
            
            if json_data.get('success', False):
                fund_data_list = json_data.get('data', [])
                for item in fund_data_list:
                    try:
                        fund_info = FundInfo.from_dict(item)
                        result_map[fund_info.fund_code] = fund_info
                    except Exception as e:
                        logger.warning(f"解析基金 {item.get('FCODE')} 详情失败: {e}")
            else:
                logger.warning(f"批量获取详情失败: {json_data.get('firstError')}")
                
        except Exception as e:
            logger.error(f"批量请求异常: {e}")
            
    return result_map

def getFundTodayTrend(user, page_size=30) -> ApiResponse[List[FundInfo]]:
    """
    获取今日基金走势信息
    
    参数:
    user: 用户对象
    page_size: 每页数量，默认为30
    
    返回:
    ApiResponse: 包含今日走势基金信息列表的响应对象
    """
    url = 'https://fundcomapi.tiantianfunds.com/mm/newCore/FundValuationList'
    
    headers = {
        "Host": "fundcomapi.tiantianfunds.com",
        "tracestate": "pid=0x1050b0820,taskid=0x1247e52c0",
        "Accept": "*/*",
        "GTOKEN": "03FC9273690F4DC4B71CB2247A0E4338",
        "clientInfo": "ttjj-iPhone18,1-iOS-iOS26.0.1",
        "MP-VERSION": "2.24.0",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Language": "zh-Hans-CN;q=1",
        "validmark": "Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdSIrQ1Lx4ygfw5br2rQnUfMES8ernsO5lB/RKZKLdR3za+zXmG+KXv2Faw8YrK/HblrMME58Nj/V4PuxEdNaVuQ==",
        "User-Agent": "EMProjJijin/6.8.3 (iPhone; iOS 26.0.1; Scale/3.00)",
        "Referer": "https://mpservice.com/fund94570b183d8ea9/release/pages/Valuation/index",
        "traceparent": "00-9f22cef31abe4424b6590e1e862f76e7-0000000000000000-01"
    }
    
    params = {
        "BUY": "true",
        "CompanyId": "",
        "DISCOUNT": "",
        "ENDNAV": "",
        "ESTABDATE": "",
        "FIELDS": "bzdm,jjjc,IsExchg,isbuy,gsz,gszzl,dwjz,jzrq,gztime,syl_1n,syl_jn",
        "PageIndex": "1",
        "PageSize": "100",
        "PageSize": "100",
        "RSBTYPE": "000001,000002,000003,000005",
        "Sort": "desc",
        "SortColumn": "gszzl",
        "ctoken": user.c_token,
        "deviceid": "F5F9C233-F56B-4ED8-8B09-CE448DB28B3C",
        "passportctoken": user.passport_ctoken,
        "passportid": user.passport_id,
        "passportutoken": user.passport_utoken,
        "plat": "Iphone",
        "product": "EFund",
        "uid": user.customer_no,
        "userid": user.customer_no
    }
    
    logger = logging.getLogger("FundTodayTrendAPI")
    
    try:
        # 使用域名而不是IP，并设置verify=False
        response = session.get(url, params=params, headers=headers, verify=False, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        
        # logger.info(f"API调用成功，返回数据: {json_data.get('success', False)}")
        
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
            # API: bzdm, jjjc, IsExchg, isbuy, gsz, gszl
            # FundInfo: FCODE, SHORTNAME, GSZ, GSZZL, ISBUY
            
            fund_name = item.get('jjjc', '')
            # 过滤掉A类基金（名称以A或a结尾）
            if fund_name and fund_name.upper().endswith('A'):
                continue
                
            fund_data = {
                'FCODE': item.get('bzdm'),
                'SHORTNAME': fund_name,
                'GSZ': item.get('gsz'),
                'GSZZL': item.get('gszzl'),
                'ISBUY': item.get('isbuy'),
                'RSFUNDTYPE': '未知', # API不返回类型
                'NAV': item.get('dwjz'), 
                'ACCNAV': 0.0, # 必填但未知
                'PDATE': item.get('jzrq'), 
                'NAVCHGRT': 0.0, # 必填但未知
                'GZTIME': item.get('gztime'),
                'SYL_1N': item.get('syl_1n'),
                'SYL_JN': item.get('syl_jn')
            }
            
            fund_info = FundInfo.from_dict(fund_data)
            indicators.append(fund_info)
            
        # 过滤重复主题的基金
        indicators = filter_duplicate_funds(indicators)
        
        # 只保留前10个
        indicators = indicators[:10]
        
        # 批量获取详细信息并补充
        if indicators:
            fund_codes = [f.fund_code for f in indicators]
            details_map = getBatchFundDetails(user, fund_codes)
            
            for fund in indicators:
                if fund.fund_code in details_map:
                    detail = details_map[fund.fund_code]
                    # 更新详细信息，保留原有的估值信息（如果详情里没有或者旧的）
                    # 注意：FundFavorInfo 返回的 GSZ/GSZZL 可能不如 FundValuationList 实时
                    # 所以我们主要更新静态信息和历史收益率
                    
                    fund.fund_type = detail.fund_type
                    fund.nav = detail.nav
                    fund.nav_date = detail.nav_date
                    fund.year_return = detail.year_return
                    fund.this_year_return = detail.this_year_return
                    fund.week_return = detail.week_return
                    fund.month_return = detail.month_return
                    fund.three_month_return = detail.three_month_return
                    fund.six_month_return = detail.six_month_return
                    # 如果详情里有估值时间且比当前的新，也可以更新估值
                    if detail.estimated_time and (not fund.estimated_time or detail.estimated_time > fund.estimated_time):
                         fund.estimated_value = detail.estimated_value
                         fund.estimated_change = detail.estimated_change
                         fund.estimated_time = detail.estimated_time
            
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
        print("正在获取今日基金走势信息...")
        # 测试API接口
        result = getFundTodayTrend(DEFAULT_USER, page_size=30)
        
        if result.Success:
            print("\n=== API调用成功 ===")
            print(f"成功状态: {result.Success}")
            print(f"数据条数: {len(result.Data) if result.Data else 0}")
            print("===================================")
            
            if result.Data:
                for i, info in enumerate(result.Data, 1):
                    print(f"{i}. {info.fund_name} ({info.fund_code})")
                    print(f"   类型: {info.fund_type}")
                    print(f"   估算涨跌幅: {info.estimated_change}%")
                    print(f"   估算净值: {info.estimated_value} ({info.estimated_time})")
                    print(f"   最新净值: {info.nav} ({info.nav_date})")
                    print(f"   今年来收益: {info.this_year_return}%")
                    print(f"   近一年收益: {info.year_return}%")
                    print(f"   是否可购买: {'是' if info.can_purchase else '否'}")
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
