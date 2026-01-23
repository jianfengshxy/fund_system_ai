import sys
import os
import json
import yaml  # 导入 yaml 模块
import logging # 导入 logging 模块
import numpy as np  # 新增：导入 numpy 模块

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
PASSPORT_CTOKEN = 'bOo9gglQX18xtG64BnG-Igsf5a-CuXf-juiDpldasTjEvqc-rZ8XOZm3FlaMbRuqO15TcdPkAxLJfDnTyZ4XK9VQ9doVEZoAF9OButgIz7II23dqvTnqFuISH0fFLN5UCMLfYM_ULPkUbgxD_WebQkAheKXB-QXBNGDiRu07R3k'
PLAN_TYPE = '1'
PASSPORT_UTOKEN = 'FobyicMgeV7VCVxp1r4B0kdVrm-y1EoJHx3-rXf1wfucAyPQk1w0-rDbUqn__OZ2Cw0i-oibZcOsklmsZ0ykpcrQ9glRksKpkatxjr4auUshSgF2LZHJuNXAphgoTjZYF6SSB71DAHZNkctNflwKrKjXU9Y9qYQ-SRl_IwkhgbknrmgaEcBrdf5JVF5Nt1O5a_ggVkk5asgXHFyXBmRWeagei7AUcAunGuh6nx6dK2bqdXsSgDFTKK_QcBKar5X9aGvLi3RG93dq3i-riQpjPaCWs0NU5nvZQuq0eeZJWfJNHjLmhbPbHZsMAHOOlF3thyskEBEZaLQ'
PHONE_TYPE = 'Android'
MOBILE_KEY = '15a16f86a738f59811cbd40da4da1d97||iemi_tluafed_me'
PAGE_INDEX = '1'
USER_ID = 'cd0b7906b53b43ffa508a99744b4055b'
U_TOKEN = 'SI789hHl4gsEAbvrI_oZ3m5qNM7jK-aHpDOWmo2xPjHuJDhmTK-wWecGNvbWp070Duh7rbDcQVxwM0YEAVxNa4WoES6DftPZ0SGCpmjsuIqC6LrZuZ1kKutk-swjGs3IRpjx5IEsUAm_D-YBC3XeuoKFMZyMiTfjixU96Jqu4u0.5'
C_TOKEN = 'xR1h5WuKZqVp9l_uzA4vmt1TbZvcuH97mfnMo8i25njxNggTR1F5Vy0FcmNOr7lcAhJSPqY1erg_deGhXFZ55j_xbVJbd19AHy1jCksXg7PjZtPuCTAF9keQTT-5TbG4qhOM6YtifyX15WE7Dn-F422CVLUdR766-RhPXoTP6laFP47mceaJCMyZyE5LawuJRkYfpEHnskeC76TmpF4ilFivNCnjiu3cnDWZsAr3k2WeAB3Cq2Su6HU3Ee5T00Np.5'
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

# -----------------------------------------------------------------------------
# DEFAULT_USER Lazy Loading Logic
# -----------------------------------------------------------------------------

def _get_password_from_yaml(account):
    try:
        s_yaml_path = os.path.join(root_dir, 's.yaml')
        if not os.path.exists(s_yaml_path):
            return None
        with open(s_yaml_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 简单正则匹配 s.yaml 中的账号密码配置
            import re
            pattern = r'"account":\s*"' + re.escape(account) + r'".*?"password":\s*"([^"]+)"'
            match = re.search(pattern, content, re.DOTALL)
            if match:
                return match.group(1)
    except Exception:
        pass
    return None

def _load_default_user():
    target_account = "13918199137"
    
    # 尝试从 s.yaml 获取密码
    password = _get_password_from_yaml(target_account)
    if not password:
        password = "sWX15706" # 默认回退密码
        
    user = None
    try:
        # 局部导入避免循环引用
        from src.service.用户管理.用户信息 import get_user_all_info
        
        # get_user_all_info 内部逻辑：内存缓存 -> 文件缓存 -> 数据库 -> 登录
        user = get_user_all_info(target_account, password)
    except Exception as e:
        print(f"Error loading default user via service: {e}")
        
    if not user:
        # 如果服务获取失败，回退到使用常量构建基础对象
        user_data = {
            'account': target_account,
            'password': password,
            'paypassword': password,
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
        user = User.from_dict(user_data)
    
    # 确保 max_hqb_bank 存在
    if not getattr(user, 'max_hqb_bank', None):
        user.max_hqb_bank = DEFAULT_HQB_BANK
        
    return user


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

# 使用 LazyConst 延迟加载 DEFAULT_USER，确保按需获取且逻辑正确
# 解决旧逻辑中可能回退到其他账号的问题，强制锁定 13918199137
DEFAULT_USER = _LazyConst(_load_default_user)

def get_bank_balance_threshold():
    """
    读取银行卡余额阈值：
    - 优先读取环境变量 BANK_BALANCE_THRESHOLD
    - 其次尝试读取本地 s.yaml 配置文件
    - 非法或未设置时回退为 300000.0
    """
    # 1. 尝试从环境变量读取
    env_val = os.environ.get('BANK_BALANCE_THRESHOLD')
    if env_val:
        try:
            val = float(env_val)
            logger.info(f"Loaded BANK_BALANCE_THRESHOLD from environment variable: {val}")
            return val
        except ValueError:
            logger.warning(f"环境变量 BANK_BALANCE_THRESHOLD 非法值: {env_val}，尝试从配置文件读取")

    # 2. 尝试从 s.yaml 读取
    try:
        yaml_path = os.path.join(root_dir, 's.yaml')
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                val = config.get('vars', {}).get('common', {}).get('props', {}).get('environmentVariables', {}).get('BANK_BALANCE_THRESHOLD')
                if val:
                    logger.info(f"Loaded BANK_BALANCE_THRESHOLD from s.yaml: {val}")
                    return float(val)
    except Exception as e:
        logger.warning(f"Failed to load s.yaml: {e}")
    
    # 3. 使用默认值
    logger.info("Using default BANK_BALANCE_THRESHOLD: 300000.0")
    return 300000.0

BANK_BALANCE_THRESHOLD = get_bank_balance_threshold()

def get_profit_threshold_for_low_balance():
    """
    读取低余额止盈收益率阈值：
    - 优先读取环境变量 PROFIT_THRESHOLD_FOR_LOW_BALANCE
    - 其次尝试读取本地 s.yaml 配置文件
    - 非法或未设置时回退为 1.0
    """
    # 1. 尝试从环境变量读取
    env_val = os.environ.get('PROFIT_THRESHOLD_FOR_LOW_BALANCE')
    if env_val:
        try:
            val = float(env_val)
            logger.info(f"Loaded PROFIT_THRESHOLD_FOR_LOW_BALANCE from environment variable: {val}")
            return val
        except ValueError:
            logger.warning(f"环境变量 PROFIT_THRESHOLD_FOR_LOW_BALANCE 非法值: {env_val}，尝试从配置文件读取")

    # 2. 尝试从 s.yaml 读取
    try:
        yaml_path = os.path.join(root_dir, 's.yaml')
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                val = config.get('vars', {}).get('common', {}).get('props', {}).get('environmentVariables', {}).get('PROFIT_THRESHOLD_FOR_LOW_BALANCE')
                if val:
                    logger.info(f"Loaded PROFIT_THRESHOLD_FOR_LOW_BALANCE from s.yaml: {val}")
                    return float(val)
    except Exception as e:
        logger.warning(f"Failed to load s.yaml: {e}")
    
    # 3. 使用默认值
    logger.info("Using default PROFIT_THRESHOLD_FOR_LOW_BALANCE: 1.0")
    return 1.0

PROFIT_THRESHOLD_FOR_LOW_BALANCE = get_profit_threshold_for_low_balance()

def get_hqb_ratio_threshold():
    """
    读取活期宝资产占比阈值：
    - 优先读取环境变量 HQB_RATIO_THRESHOLD
    - 其次尝试读取本地 s.yaml 配置文件
    - 非法或未设置时回退为 20.0
    """
    # 1. 尝试从环境变量读取
    env_val = os.environ.get('HQB_RATIO_THRESHOLD')
    if env_val:
        try:
            val = float(env_val)
            logger.info(f"Loaded HQB_RATIO_THRESHOLD from environment variable: {val}")
            return val
        except ValueError:
            logger.warning(f"环境变量 HQB_RATIO_THRESHOLD 非法值: {env_val}，尝试从配置文件读取")

    # 2. 尝试从 s.yaml 读取
    try:
        yaml_path = os.path.join(root_dir, 's.yaml')
        if os.path.exists(yaml_path):
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                val = config.get('vars', {}).get('common', {}).get('props', {}).get('environmentVariables', {}).get('HQB_RATIO_THRESHOLD')
                if val:
                    logger.info(f"Loaded HQB_RATIO_THRESHOLD from s.yaml: {val}")
                    return float(val)
    except Exception as e:
        logger.warning(f"Failed to load s.yaml: {e}")
    
    # 3. 使用默认值
    logger.info("Using default HQB_RATIO_THRESHOLD: 20.0")
    return 20.0

HQB_RATIO_THRESHOLD = get_hqb_ratio_threshold()

def _load_qiu_xiaoyu():
    from src.service.用户管理.用户信息 import get_user_all_info
    return get_user_all_info("13918797997", "Zj951103")

# 模块级“常量”：惰性加载，使用/打印时才真正获取用户信息
QIU_XIAOYU = _LazyConst(_load_qiu_xiaoyu)

if __name__ == '__main__':
    # 运行脚本时打印常量的实际值
    # print(QIU_XIAOYU)
    print(DEFAULT_USER)
    # print(DEFAULT_FUND_PLAN_DETAIL)
