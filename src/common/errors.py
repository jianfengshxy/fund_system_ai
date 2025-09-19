class TradePasswordError(Exception):
    """交易/支付密码错误，属于不可重试错误，需立刻中止流程。"""
    pass