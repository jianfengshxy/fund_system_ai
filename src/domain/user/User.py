import hashlib
import logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class User:
    def __init__(self, account, password, paypassword=None):
        self.account = account
        self.password = password
        self.paypassword = paypassword
        self.c_token = ""
        self.u_token = ""
        self.customer_no = ""
        self.customer_name = ""
        self.index = ""
        self.passport_id = ""
        self.passport_uid = ""
        self.passport_ctoken = ""
        self.passport_utoken = ""
        self.need_verify_code_next = ""
        self.total_fund_asset = 0.0
        self.hqb_value = 0.0
        self.total_value = 0.0
        self.max_hqb_bank = None  # 添加max_hqb_bank属性初始化

    @classmethod
    def from_dict(cls, data):
        user = cls(
            account=data.get('account'),
            password=data.get('password'),
            paypassword=data.get('paypassword')
        )
        user.c_token = data.get('c_token', '')
        user.u_token = data.get('u_token', '')
        user.customer_no = data.get('customer_no', '')
        user.customer_name = data.get('customer_name', '')
        user.index = data.get('index', '')
        user.passport_id = data.get('passport_id', '')
        user.passport_uid = data.get('passport_uid', '')
        user.passport_ctoken = data.get('passport_ctoken', '')
        user.passport_utoken = data.get('passport_utoken', '')
        user.need_verify_code_next = data.get('need_verify_code_next', True)
        user.total_fund_asset = float(data.get('total_fund_asset', 0.0))
        user.hqb_value = float(data.get('hqb_value', 0.0))
        user.total_value = float(data.get('total_value', 0.0))
        return user

    @classmethod
    def create_with_tokens(cls, account, password, c_token, u_token, customer_no):
        user = cls(account, password)
        user.c_token = c_token
        user.u_token = u_token
        user.customer_no = customer_no
        return user

    def __repr__(self):
        return f"""User(
            account={self.account},
            password={self.password},
            paypassword={self.paypassword},
            c_token={self.c_token},
            u_token={self.u_token},
            customer_no={self.customer_no},
            customer_name={self.customer_name},
            index={self.index},
            passport_id={self.passport_id},
            passport_uid={self.passport_uid},
            passport_ctoken={self.passport_ctoken},
            passport_utoken={self.passport_utoken},
            max_hqb_bank={self.max_hqb_bank}
        )"""