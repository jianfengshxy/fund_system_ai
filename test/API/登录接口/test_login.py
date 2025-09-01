import pytest
from src.API.登录接口.login import login
from src.domain.user import User

@pytest.mark.skip(reason="手工指定调用")
def test_login_success():
    """测试登录成功的情况"""
    print("开始测试登录成功")
    
    result = login("13918199137", "sWX15706")
    print(f"登录响应结果: {result}")
    # Only proceed with other assertions if previous checks pass
    assert result.customer_no == "cd0b7906b53b43ffa508a99744b4055b"
    assert result.customer_name == "施小雨"
    assert result.mobile_phone == "139****9137"
    assert result.risk == "5"
    assert result.risk_name == "积极进取型"
    assert result.vip_level == 5
    assert result.index == 5
    print("登录成功验证通过")

def test_login_failed_with_wrong_password():
    """测试密码错误的情况"""
    print("开始测试密码错误登录")
    
    result = login("13918199137", "wrong_password")
    print(f"登录响应结果: {result}")
    
    assert result is None
    print("密码错误验证通过")

def test_login_failed_with_wrong_account():
    """测试账号错误的情况"""
    print("开始测试账号错误登录")
    
    # 修改这一行，使用相对导入而不是绝对导入
    result = login("13900000000", "any_password")
    print(f"登录响应结果: {result}")
    
    assert result is None
    print("账号错误验证通过")