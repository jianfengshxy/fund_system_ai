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


def pytest_addoption(parser):
    parser.addoption("--run-integration", action="store_true", default=False)


def pytest_ignore_collect(path, config):
    run_integration = bool(config.getoption("--run-integration")) or os.environ.get("RUN_INTEGRATION") == "1"
    if run_integration:
        return False
    p = str(path)
    if f"{os.sep}test{os.sep}unit{os.sep}" in p:
        return False
    if any(
        seg in p
        for seg in [
            f"{os.sep}test{os.sep}API{os.sep}",
            f"{os.sep}test{os.sep}service{os.sep}",
            f"{os.sep}test{os.sep}bussiness{os.sep}",
            f"{os.sep}test{os.sep}db{os.sep}",
        ]
    ):
        return True
    return False


def pytest_collection_modifyitems(config, items):
    run_integration = bool(config.getoption("--run-integration")) or os.environ.get("RUN_INTEGRATION") == "1"
    for item in items:
        p = str(getattr(item, "fspath", ""))
        if any(
            seg in p
            for seg in [
                f"{os.sep}test{os.sep}API{os.sep}",
                f"{os.sep}test{os.sep}service{os.sep}",
                f"{os.sep}test{os.sep}bussiness{os.sep}",
                f"{os.sep}test{os.sep}db{os.sep}",
            ]
        ):
            item.add_marker(pytest.mark.integration)
            if not run_integration:
                item.add_marker(pytest.mark.skip(reason="integration test (set RUN_INTEGRATION=1 or --run-integration)"))
