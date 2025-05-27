from typing import Optional
from domain.user import ApiResponse

class SubAccountResponse:
    def __init__(self,
                 sub_account_app_no: str = '',
                 user_id: str = '',
                 last_close_time: Optional[str] = None,
                 open_state: int = 0,
                 sub_account_no_idea: Optional[str] = None,
                 customize_property: Optional[str] = None,
                 followed_customer_no: Optional[str] = None,
                 followed_sub_account_no: Optional[str] = None,
                 property: str = '',
                 manual_review_state: int = 0,
                 style: str = '',
                 create_time: str = '',
                 is_enabled: bool = False,
                 state: int = 0,
                 name: str = '',
                 alias: Optional[str] = None,
                 sub_account_no: str = '',
                 update_time: str = '',
                 manual_review_field: str = ''):
        self.sub_account_app_no = sub_account_app_no
        self.user_id = user_id
        self.last_close_time = last_close_time
        self.open_state = open_state
        self.sub_account_no_idea = sub_account_no_idea
        self.customize_property = customize_property
        self.followed_customer_no = followed_customer_no
        self.followed_sub_account_no = followed_sub_account_no
        self.property = property
        self.manual_review_state = manual_review_state
        self.style = style
        self.create_time = create_time
        self.is_enabled = is_enabled
        self.state = state
        self.name = name
        self.alias = alias
        self.sub_account_no = sub_account_no
        self.update_time = update_time
        self.manual_review_field = manual_review_field