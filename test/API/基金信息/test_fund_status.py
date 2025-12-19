
import sys
import os
import logging
import json
import requests

# Adjust path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.common.constant import DEFAULT_USER, SERVER_VERSION, PHONE_TYPE

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_fund_fields(fund_code):
    url = 'https://fundcomapi.tiantianfunds.com/mm/FundFavor/FundFavorInfo'
    
    headers = {
        'Accept': '*/*',
        'User-Agent': 'okhttp/3.12.13',
        'clientInfo': 'ttjj-ZTE 7534N-Android-11',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://mpservice.com/770ddc37537896dae8ecd8160cb25336/release/pages/fundList/all-list/index'
    }
    
    # Try more fields
    fields = 'MAXSG,FCODE,SHORTNAME,ISBUY,STATUS,FUNDSTATE,IS_REDEEM,CAN_REDEEM,IS_BUY,BuyStatus,RedeemStatus,RSSTATUS'
    
    data = {
        'FIELDS': fields,
        'product': 'EFund',
        'APPID': 'FAVOR,FAVOR_ED,FAVOR_GS',
        'pageSize': 20,
        'passportctoken': DEFAULT_USER.passport_ctoken,
        'passportutoken': DEFAULT_USER.passport_utoken,
        'deviceid': '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me',
        'userid': DEFAULT_USER.customer_no,
        'version': SERVER_VERSION,
        'ctoken': DEFAULT_USER.c_token,
        'uid': DEFAULT_USER.customer_no,
        'CODES': fund_code,
        'pageIndex': 1,
        'utoken': DEFAULT_USER.u_token,
        'plat': PHONE_TYPE,
        'passportid': DEFAULT_USER.passport_id
    }
    
    try:
        response = requests.post(
            url,
            data=data,
            headers=headers,
            verify=False,
            timeout=10
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_fund_fields('008706')
