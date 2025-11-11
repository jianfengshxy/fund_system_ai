import sys
import os
import numpy as np  # 新增：导入 numpy 模块

# 如果需要定义一个类似 Null 的常量，可以使用 None 或自定义常量
NULL_VALUE = None

# 添加项目根目录到路径
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# 使用相对导入而不是绝对导入
from src.domain.user.User import User
from src.domain.bank.bank import BankCard, HqbBank, BankApiResponse
from src.domain.fund_plan.fund_plan import FundPlan
from src.domain.fund_plan.fund_plan_detail import FundPlanDetail
from src.domain.trade.share import Share

# API请求参数常量
SERVER_VERSION = '6.7.1'
PAGE_SIZE = '100'
DEVICE_ID = '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me'
PASSPORT_CTOKEN = 'CR0PL-qa8w6SmCGBL4KzSXeTioFwoR7HN_JmcR_yMVCGSVFCGYTR4KBYc8gQI5rUPIp-fs6Hg5yN6jIPAYli_sE4Fnm-S2TN298wRuSBAxzWaDoRd82XYXt7FuPkh57WzKu7ejHQrhMXwp-uR5zuPnQi2L1joI7KuE0jnW4Yl2E'
PLAN_TYPE = '1'
PASSPORT_UTOKEN = 'QjaJ8B6U43EzrU9QuBKxUcLl7plJD3DQnGBVESjw_tEyqhKYNefuSoxE23M_B7Jf3J0QXt9K8L11-c8kM0US8Dh8-cOaAbUY9-Grz_lOD6YHTQVF-VrpwJ3rltTFJyrpYlAiTIjmOCCKRTAZHnZpLu0sRlqnHr8eQboojFxiYI6iO6kzsJMrP02LvOzw4P_nGXUk8trx06j9Y2RFXx950V04nn1NMRjyTSRUNbPKmwTYeaI1PGmptAYRY16wQzraxG8vMqmV8HoG5zVi9ovBuh0H3rBpfAMvAPsQpNSkMYs83gdJjuXZi4pY133FWRGdIG-1Hula3rHsjdvZm56ZkLT4UjljRP3aoFZ7N_zbM-g'
PHONE_TYPE = 'Android'
MOBILE_KEY = '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me'
PAGE_INDEX = '1'
USER_ID = 'cd0b7906b53b43ffa508a99744b4055b'
U_TOKEN = 'CTZAr6Vx9U6SCvZEIZ5zmTvaG8t53DNGjfLyDr-paGMyqI-sh4QTKVawSW82SgLIU1eNn25zIksAj3J82S29TNDksOhD93p2HYuiCWB4IL_9H2J4kelucqM__eoWiXjeCCvzTvVdQGjG6c4UCVseea4jLsXm2ANQf30bIdlb1P8.5'
C_TOKEN = 'xR1h5WuKZqVp9l_uzA4vmt1TbZvcuH97mfnMo8i25njxNggTR1F5Vy0FcmNOr7lcAhJSPqY1erg_deGhXFZ55j_xbVJbd19AHy1jCksXg7PjZtPuCTAF9keQTT-5TbG4qhOM6YtifyX15WE7Dn-F40DXYm8s_vSUBewq1S4OlzwT4k3mTLaIC4fUIttpmCxjUWgWeHBzBKLOkrYF1bvmidcxfd9G6pCYskXwInJcWiUqGVfJjWkRd1FXly1YR8og.5'
PASSPORT_ID = '8461315737102942'
NAME = '施小雨'
PLAN_ID = '2e82e7fa28d34c99a3b3abb072b880bc'
FUND_CODE = '020256'

# 定义默认的活期宝银行卡数据
DEFAULT_HQB_BANK_DATA = {
    'AccountNo': 'f12a70addec7458dae41369ac1005e5a',
    'BankCardNo': '6222***********8882',
    'BankCode': '002',
    'BankName': '工商银行',
    'BankType': '0',
    'BankState': True,
    'BankAvaVol': "170643.97",
    'CurrentRealBalance': 277397.86,
    'HasBranch': True,
    'ShowBankCode': '002',
    'BankCardType': '储蓄卡',
    'AccountState': 1,
    'CanPayment': True,
    'EnableTips': False,
    'Tips': None,
    'EnableChannelTips': False,
    'ChannelTips': None,
    'RechargeTitle': None,
    'Title': None,
    'OpenTime': None,
    'CreateTime': None
}

# 创建默认的活期宝银行卡常量对象
DEFAULT_HQB_BANK = HqbBank.from_dict(DEFAULT_HQB_BANK_DATA)

# 定义默认的基金定投计划详情数据
DEFAULT_FUND_PLAN_DETAIL_DATA = {
    'rationPlan': {
        'planId': 'fb5f5ee06eb941258f2fd6965cab32b4',
        'fundCode': '017968',
        'fundName': '华富科技动能混合C',
        'fundType': '4',
        'planState': 0,
        'planBusinessState': '10',
        'pauseType': None,
        'planExtendStatus': '13',
        'planType': '',
        'periodType': 4,
        'periodValue': 1,
        'amount': 2000.0,
        'bankAccountNo': 'f12a70addec7458dae41369ac1005e5a',
        'payType': 1,
        'subAccountNo': '28010355',
        'subAccountName': '目标止盈定投017968',
        'currentDay': '2025-05-22',
        'buyStrategy': '1',
        'redeemStrategy': '1',
        "planAssets": 5754.14,
        "rationProfit": -246.73,
        "totalProfit": -246.73,
        "rationProfitRate": -0.0411,
        "totalProfitRate": -0.0411,
        "unitPrice": 1.382,
        "targetRate": "5%",
        'retreatPercentage': None,
        'renewal': True,
        'redemptionWay': 1,
        'planStrategyId': 'CL001',
        'redeemLimit': '1',
        'financialType': '',
        'executedAmount': 4000.0,
        'executedTime': 2,
        'nextDeductDescription': '',
        'nextDeductDate': None,
        'reTriggerDate': '1900-01-01',
        'recentDeductDate': '2025-05-23',
        'bankCode': '002',
        'showBankCode': '002',
        'shortBankCardNo': '8882',
        'subDisband': None,
        'isGdlc': False,
        'retriggerTips': '',
        'isDeductDay': False
    },
    'profitTrends': [
        {
            'date': '2025-05-08',
            'profitRate': 0,
            'unitPrice': 1.3963,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-09',
            'profitRate': -0.023,
            'unitPrice': 1.3963,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-12',
            'profitRate': 0.0064,
            'unitPrice': 1.3963,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-13',
            'profitRate': -0.0028,
            'unitPrice': 1.3963,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-14',
            'profitRate': -0.0152,
            'unitPrice': 1.3963,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-15',
            'profitRate': -0.0156,
            'unitPrice': 1.382,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-16',
            'profitRate': 0.0125,
            'unitPrice': 1.382,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-19',
            'profitRate': -0.0065,
            'unitPrice': 1.382,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-20',
            'profitRate': -0.0186,
            'unitPrice': 1.382,
            'buyPoint': False,
            'redeemPoint': False
        },
        {
            'date': '2025-05-21',
            'profitRate': -0.0282,
            'unitPrice': 1.382,
            'buyPoint': False,
            'redeemPoint': False
        }
    ],
    'couponDetail': None,
    'shares': [
        {
            'availableVol': 4342.09,
            'bankCode': '002',
            'showBankCode': '002',
            'bankCardNo': 'PR28010355Z6222021104005268882',
            'bankName': '工商银行',
            'shareId': '1724705588',
            'bankAccountNo': 'f12a70addec7458dae41369ac1005e5a',
            'totalVol': 4342.09
        }
    ]
}

# 创建FundPlan对象
DEFAULT_FUND_PLAN = FundPlan(
    planId=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planId'],
    fundCode=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['fundCode'],
    fundName=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['fundName'],
    fundType=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['fundType'],
    planState=str(DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planState']),
    planBusinessState=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planBusinessState'],
    pauseType=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['pauseType'],
    planExtendStatus=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planExtendStatus'],
    planType=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planType'],
    periodType=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['periodType'],
    periodValue=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['periodValue'],
    amount=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['amount'],
    bankAccountNo=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['bankAccountNo'],
    payType=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['payType'],
    subAccountNo=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['subAccountNo'],
    subAccountName=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['subAccountName'],
    currentDay=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['currentDay'],
    buyStrategy=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['buyStrategy'],
    redeemStrategy=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['redeemStrategy'],
    planAssets=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planAssets'],
    rationProfit=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['rationProfit'],
    totalProfit=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['totalProfit'],
    rationProfitRate=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['rationProfitRate'],
    totalProfitRate=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['totalProfitRate'],
    unitPrice=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['unitPrice'],
    targetRate=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['targetRate'],
    retreatPercentage=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['retreatPercentage'],
    renewal=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['renewal'],
    redemptionWay=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['redemptionWay'],
    planStrategyId=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['planStrategyId'],
    redeemLimit=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['redeemLimit'],
    financialType=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['financialType'],
    executedAmount=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['executedAmount'],
    executedTime=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['executedTime'],
    nextDeductDescription=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan'].get('nextDeductDescription', ''),
    nextDeductDate=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['nextDeductDate'],
    reTriggerDate=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['reTriggerDate'],
    recentDeductDate=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['recentDeductDate'],
    bankCode=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['bankCode'],
    showBankCode=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['showBankCode'],
    shortBankCardNo=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['shortBankCardNo'],
    subDisband=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['subDisband'],
    isGdlc=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['isGdlc'],
    retriggerTips=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['retriggerTips'],
    isDeductDay=DEFAULT_FUND_PLAN_DETAIL_DATA['rationPlan']['isDeductDay']
)

# 创建Share对象
DEFAULT_SHARES = [
    Share(**share_data)
    for share_data in DEFAULT_FUND_PLAN_DETAIL_DATA['shares']
]

# 创建FundPlanDetail对象
DEFAULT_FUND_PLAN_DETAIL = FundPlanDetail(
    rationPlan=DEFAULT_FUND_PLAN,
    profitTrends=DEFAULT_FUND_PLAN_DETAIL_DATA['profitTrends'],
    couponDetail=DEFAULT_FUND_PLAN_DETAIL_DATA['couponDetail'],
    shares=DEFAULT_SHARES
)

user_data = {
    'account': '13918199137',
    'password': 'sWX15706',
    'paypassword': 'sWX15706',
    'c_token': C_TOKEN,
    'u_token': U_TOKEN,
    'customer_no': USER_ID,
    'customer_name': NAME,
    'index': '5',
    'passport_id': PASSPORT_ID,
    'passport_uid': PASSPORT_ID,
    'passport_ctoken': PASSPORT_CTOKEN,
    'passport_utoken': PASSPORT_UTOKEN,
}

# 创建默认用户对象并设置默认活期宝银行卡
DEFAULT_USER = User.from_dict(user_data)
DEFAULT_USER.max_hqb_bank = DEFAULT_HQB_BANK

# 获取用户对象
class _LazyConst:
    def __init__(self, loader):
        self._loader = loader
        self._value = None
        self._loaded = False

    def value(self):
        if not self._loaded:
            self._value = self._loader()
            self._loaded = True
        return self._value

    def __getattr__(self, name):
        return getattr(self.value(), name)

    def __repr__(self):
        return repr(self.value())

    def __str__(self):
        return str(self.value())

def _load_qiu_xiaoyu():
    from src.service.用户管理.用户信息 import get_user_all_info
    return get_user_all_info("13918797997", "Zj951103")

# 模块级“常量”：惰性加载，使用/打印时才真正获取用户信息
QIU_XIAOYU = _LazyConst(_load_qiu_xiaoyu)

if __name__ == '__main__':
    # 运行脚本时打印常量的实际值
    print(QIU_XIAOYU)
    print(DEFAULT_USER)
    # print(DEFAULT_FUND_PLAN_DETAIL)