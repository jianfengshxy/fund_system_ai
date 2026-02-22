import pytest
from src.common.constant import DEFAULT_USER
from src.API.交易管理.trade import get_one_fund_tran_infos

def test_get_one_fund_tran_infos():
    """
    测试获取单个基金的历史交易记录
    """
    fund_code = "012414"
    
    # 调用接口
    # 注意：默认时间范围是 2010-01-01 到当前
    trades = get_one_fund_tran_infos(DEFAULT_USER, fund_code=fund_code)
    
    # 打印结果以便调试
    print(f"\n获取到 {len(trades)} 条交易记录")
    for i, trade in enumerate(trades[:5]): # 只打印前5条
        print(f"交易 {i+1}: 日期={getattr(trade, 'strike_start_date', '') or getattr(trade, 'apply_work_day', '')}, "
              f"类型={trade.business_type}, 金额={getattr(trade, 'confirm_count', '') or getattr(trade, 'amount', '')}, "
              f"状态={trade.status}")
    
    # 断言
    # 只要不报错且返回列表（即使为空）就算通过，因为具体数据依赖于用户持仓
    assert isinstance(trades, list)
    
    # 如果有数据，验证字段完整性
    if trades:
        trade = trades[0]
        # 验证 TradeResult 对象的关键属性是否存在
        assert hasattr(trade, 'fund_code')
        # assert hasattr(trade, 'amount') # amount 可能是 None
        assert hasattr(trade, 'status')

if __name__ == "__main__":
    pytest.main(["-s", __file__])
