import os
import sys
import pytest

# 获取项目根目录路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 如果项目根目录不在Python路径中，则添加
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.user.User import User
# 在这里添加通用的fixtures
@pytest.fixture
def DEFAULT_USER():
    return User(
        customer_no="cd0b7906b53b43ffa508a99744b4055b",
        mobile_phone="13918199137"
    )
