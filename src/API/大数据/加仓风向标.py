import logging
import requests
from typing import Dict, Any

if __name__ == "__main__":
    import os
    import sys

    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

from src.common.constant import (
    DEFAULT_GTOKEN,
    DEFAULT_USER,
    IOS_CLIENT_INFO,
    IOS_USER_AGENT,
    MOBILE_KEY,
    PLATFORM,
    SERVER_VERSION,
    describe_rs_fund_type,
    describe_rs_sub_fund_type,
    format_type_with_label,
)
from src.common.requests_session import session
from src.domain.fund_plan import ApiResponse

def getFundInvestmentIndicators(user, page_size=20) -> ApiResponse[Dict[str, Any]]:
    """
    获取“加仓风向标”基金列表的原始结果。

    返回结果中的关键字段：
    - `RSFUNDTYPE`: 天天基金一级分类，如 `000/001/002/007`
    - `RSBTYPE`: 天天基金二级分类，如 `000001/002001/002004/007001`
    - `PRODUCT_RANK`: 在当前配置榜单里的排序
    - `SYL_1N`: 近 1 年收益率
    - `SYL_LN`: 成立以来收益率

    注意：
    - `RSFUNDTYPE` 和资产接口里的 `FundType` 不是同一套编码，不能混用。
    - `RSBTYPE` 是天天基金的二级分类，比 `RSFUNDTYPE` 更细。
    """
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundCustom/multiFundTypeSpeConfigListPage'
    
    headers = {
        'Connection': 'keep-alive',
        'Content-Type': 'application/x-www-form-urlencoded',
        'validmark': 'Li4RtWc+9LvmhgcBNN3qg3dzZjFUt4WiApOOGmkaVZL5BWm0DcGX9NZYIxjsAsZdVcHJ8J2NdZhXTNMQR9BMpxG3EMlqXyJoFeiMLZWZZtJ1DXqiIOSu/kLYsAt37vKDllijg7ffsKY6LcVX2IpgamPZG7YN4mKd7mTYGSc0Sjg=',
        'mp_instance_id': '68',
        'Referer': 'https://mpservice.com/fund9bb5726fafc14e/release/pages/home/index',
        'gtoken': DEFAULT_GTOKEN,
        'clientInfo': IOS_CLIENT_INFO,
        'traceparent': '00-0000000046aa4cae0000019426368b65-0000000000000000-01',
        'tracestate': 'pid=0x9cf938d,taskid=0x25b8739',
        'Host': 'fundcomapi.tiantianfunds.com',
        'User-Agent': IOS_USER_AGENT
    }
    
    data = {
        'FIELDS': 'SHORTNAME,RSFUNDTYPE,RSBTYPE,SYL_1N,SYL_LN,FCODE,EUTIME',
        'product': 'EFund',
        'pageSize': page_size,
        'passportctoken': user.passport_ctoken,
        'configType': '9',
        'passportutoken': user.passport_utoken,
        'deviceid': MOBILE_KEY,
        'userid': user.customer_no,
        'version': SERVER_VERSION,
        'configSort': 'asc',
        'configSortColumn': 'PRODUCT_RANK',
        'ctoken': user.c_token,
        'uid': user.customer_no,
        'utoken': user.u_token,
        'plat': PLATFORM,
        'passportid': user.passport_id
    }
    
    logger = logging.getLogger("FundInvestmentIndicatorAPI")
    
    try:
        response = session.post(url, data=data, headers=headers, verify=False, timeout=30)
        response.raise_for_status()
        json_data = response.json()
        
        logger.info(f"API调用成功，返回数据: {json_data.get('success', False)}")
        
        return ApiResponse(
            Success=json_data.get('success', False),
            ErrorCode=json_data.get('errorCode'),
            Data=json_data.get('data'),
            FirstError=json_data.get('firstError'),
            DebugError=json_data.get('hasWrongToken')
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
    
    try:
        # 测试API接口
        result = getFundInvestmentIndicators(DEFAULT_USER, page_size=20)
        
        if result.Success:
            print("\n=== API调用成功 ===")
            print(f"成功状态: {result.Success}")
            print(f"错误代码: {result.ErrorCode if result.ErrorCode else '无'}")
            fund_list = (result.Data or {}).get("9", [])
            print(f"榜单条数: {len(fund_list)}")
            print("字段说明:")
            print("  RSFUNDTYPE: 天天基金一级分类")
            print("  RSBTYPE: 天天基金二级分类")
            print("  PRODUCT_RANK: 榜单排序")
            print("  SYL_1N: 近1年收益率")
            print("  SYL_LN: 成立以来收益率")
            print("  EUTIME: 数据更新时间")
            print("")

            for index, item in enumerate(fund_list, start=1):
                rs_fund_type = item.get("RSFUNDTYPE")
                rs_sub_type = item.get("RSBTYPE")
                print(f"#{index}")
                print(f"  基金: {item.get('SHORTNAME')} ({item.get('FCODE')})")
                print(f"  一级分类 RSFUNDTYPE: {format_type_with_label(rs_fund_type, describe_rs_fund_type(rs_fund_type))}")
                print(f"  二级分类 RSBTYPE: {format_type_with_label(rs_sub_type, describe_rs_sub_fund_type(rs_sub_type))}")
                print(f"  榜单排名 PRODUCT_RANK: {item.get('PRODUCT_RANK')}")
                print(f"  近1年收益率 SYL_1N: {item.get('SYL_1N')}")
                print(f"  成立以来收益率 SYL_LN: {item.get('SYL_LN')}")
                print(f"  更新时间 EUTIME: {item.get('EUTIME')}")
                print("-" * 50)
        else:
            print("\n=== API调用失败 ===")
            print(f"错误代码: {result.ErrorCode}")
            print(f"错误信息: {result.FirstError}")
            if result.DebugError:
                print(f"调试错误: {result.DebugError}")
    except Exception as e:
        print("\n=== 执行过程中发生异常 ===")
        print(f"异常信息: {str(e)}")
