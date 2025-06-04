import sys
import os
import logging
import urllib.parse
import urllib3
import warnings
import json
import time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from common.constant import SERVER_VERSION, PHONE_TYPE

# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 禁用 urllib3 的警告信息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import requests
from typing import Optional
from domain.fund.fund_info import FundInfo

def getFundInfo(user,fund_code) -> Optional[FundInfo]:
    """
    获取基金信息
    Args:
        user: User对象，包含用户认证信息
        fund_code: 基金代码
    Returns:
        FundInfo: 基金信息对象，如果获取失败返回None
    """
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundFavor/FundFavorInfo'
    
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Host': 'fundcomapi.tiantianfunds.com',
        # 移除包含中文的 Referer 头，这是导致编码错误的主要原因
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'forceLog': '1',
        'gtoken': 'ceaf-4a997831b1b3b90849f585f98ca6f30e',
        'mp_instance_id': '32',
        'traceparent': '00-0000000046aa4cae00000196718a8166-0000000000000000-01',
        'tracestate': 'pid=0x6f96620,taskid=0xabc5123',
        'Content-Type': 'application/x-www-form-urlencoded',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1DXqiIOSu/kLYsAt37vKDFhzWESfp9O5+28eHlMZFdAOKtOr630iFFehhF8ZZ2O0='
    }
    
    # 使用不包含中文字符的 Referer
    referer = 'https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/all-list/index'
    headers['Referer'] = referer
    
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
        'CODES': fund_code,
        'pageIndex': 1,
        'utoken': user.u_token,
        'Sort': '',
        'plat': PHONE_TYPE,
        'passportid': user.passport_id
    }
    
    logger = logging.getLogger("FundInfo")
    try:
        # 直接使用原始数据，不进行额外编码
        response = requests.post(
            url,
            data=data,
            headers=headers,
            verify=False,
            timeout=10
        )
        
        # 检查响应状态码
        response.raise_for_status()
        
        # 使用utf-8解码响应内容
        response_text = response.content.decode('utf-8')
        
        try:
            json_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("JSON解析失败: %s, 响应内容: %s", str(e), response_text[:200])
            return None
            
        logger.debug("响应数据: %s", json.dumps(json_data, ensure_ascii=False))
        
        if not json_data.get('success', False):
            error_msg = json_data.get('firstError', '未知错误')
            logger.error("获取基金信息失败: %s", error_msg)
            return None
            
        fund_data = json_data.get('data', [])
        if not fund_data:
            logger.error("未找到基金信息")
            return None
            
        try:
            fund_info_data = fund_data[0]
            fund_info = FundInfo.from_dict(fund_info_data)
            fund_info = updateFundEstimatedValue(fund_info)
            return fund_info
        except (IndexError, KeyError, TypeError) as e:
            logger.error("解析基金数据失败: %s", str(e))
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error('请求失败: %s', str(e))
        return None
    except Exception as e:
        logger.error('处理过程发生异常: %s', str(e))
        import traceback
        logger.error('异常堆栈: %s', traceback.format_exc())
        return None

def updateFundEstimatedValue(fund_info: FundInfo) -> Optional[FundInfo]:
    """
    更新基金的估值信息
    Args:
        fund_info: FundInfo对象
    Returns:
        更新后的FundInfo对象，如果更新失败返回None
    """
    url = f'https://fundgz.1234567.com.cn/js/{fund_info.fund_code}.js'
    params = {
        'rt': int(time.time() * 1000)  # 添加时间戳防止缓存
    }
    
    headers = {
        'Connection': 'keep-alive',
        'Host': 'fundgz.1234567.com.cn',
        'User-Agent': 'Apache-HttpClient/4.5.14 (Java/17.0.10)'
    }
    
    logger = logging.getLogger("FundInfo")
    
    # 添加重试机制
    max_retries = 3
    retry_count = 0
    retry_delay = 2  # 初始延迟2秒
    
    while retry_count < max_retries:
        try:
            if retry_count > 0:
                logger.debug(f"正在进行第 {retry_count} 次重试获取基金估值数据，基金代码: {fund_info.fund_code}")
                # 指数退避策略，每次重试延迟时间翻倍
                time.sleep(retry_delay)
                retry_delay *= 2
                
            response = requests.get(url, params=params, headers=headers, verify=False, timeout=10)
            response.raise_for_status()
            
            # 响应格式为: jsonpgz({...});，需要提取JSON部分
            content = response.text
            if content.strip() == "jsonpgz();":
                logger.info(f"{fund_info.fund_name}响应为空，设置估算涨跌为0.0")
                fund_info.estimated_change = 0.0
                return fund_info
            
            json_str = content[content.find('{'): content.rfind('}')+1]
            
            try:
                data = json.loads(json_str)
                
                # 更新估值信息
                fund_info.estimated_value = float(data.get('gsz', 0))  # GSZ - 估算净值
                fund_info.estimated_change = float(data.get('gszzl', 0))  # GSZZL - 估算涨跌幅
                fund_info.estimated_time = data.get('gztime', '')  # GZTIME - 估算时间                
                
                # 更新收益率信息 - 原有收益率加上估算涨跌幅                
                if fund_info.week_return is not None:
                    fund_info.week_return = fund_info.week_return + fund_info.estimated_change
                if fund_info.month_return is not None:
                    fund_info.month_return = fund_info.month_return + fund_info.estimated_change
                if fund_info.three_month_return is not None:
                    fund_info.three_month_return = fund_info.three_month_return + fund_info.estimated_change
                if fund_info.six_month_return is not None:
                    fund_info.six_month_return = fund_info.six_month_return + fund_info.estimated_change
                if fund_info.year_return is not None:
                    fund_info.year_return = fund_info.year_return + fund_info.estimated_change
                if fund_info.this_year_return is not None:
                    fund_info.this_year_return = fund_info.this_year_return + fund_info.estimated_change
                       
                # 请求成功，返回更新后的基金信息
                if retry_count > 0:
                    logger.debug(f"重试成功，已获取基金 {fund_info.fund_code} 的估值数据")
                return fund_info
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"解析估值数据失败: {str(e)}")
                logger.error(f"原始响应数据: {content}")
                retry_count += 1
                continue
                
        except requests.exceptions.RequestException as e:
            logger.error(f'获取估值数据失败: {str(e)}')
            retry_count += 1
            # 如果是最后一次重试仍然失败
            if retry_count >= max_retries:
                logger.error(f"基金 {fund_info.fund_code} 估值数据获取失败，已重试 {max_retries} 次")
                return None
            continue
        except Exception as e:
            logger.error(f'更新估值信息时发生异常: {str(e)}')
            retry_count += 1
            if retry_count >= max_retries:
                return None
            continue
    
    # 所有重试都失败
    return None



if __name__ == "__main__":
    import logging
    from common.constant import DEFAULT_USER, FUND_CODE
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 获取基金信息
        fund_info = getFundInfo(DEFAULT_USER, '011707')
        
        if fund_info:
            print("\n基金信息获取成功:")
            print(f"基金代码: {fund_info.fund_code}")
            print(f"基金名称: {fund_info.fund_name}")
            print(f"基金类型: {fund_info.fund_type}")
            print(f"当前净值: {fund_info.nav}")
            print(f"净值日期: {fund_info.nav_date}")
            print(f"日涨跌幅: {fund_info.nav_change}%")
            print(f"估算时间: {fund_info.estimated_time}")
            print(f"估算净值: {fund_info.estimated_value or '暂无'}")
            print(f"估算涨跌: {fund_info.estimated_change or '暂无'}%")
            print(f"近一周收益: {fund_info.week_return or '暂无'}%")
            print(f"近一月收益: {fund_info.month_return or '暂无'}%")
            print(f"近三月收益: {fund_info.three_month_return or '暂无'}%")
            print(f"今年收益: {fund_info.this_year_return or '暂无'}%")
            print(f"是否可购买: {'是' if fund_info.can_purchase else '否'}")
        else:
            print("\n获取基金信息失败")
            
    except Exception as e:
        print(f"\n程序执行出错: {str(e)}")




