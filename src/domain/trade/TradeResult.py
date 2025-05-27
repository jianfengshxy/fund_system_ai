class TradeResult:
    def __init__(self, busin_serial_no, business_type, apply_workday=None, apply_amount=None, status=None, show_com_prop=None, fund_code=None):
        self.busin_serial_no = busin_serial_no
        self.business_type = business_type
        self.apply_work_day = apply_workday
        self.amount = apply_amount
        self.status = status
        self.show_com_prop = show_com_prop
        self.fund_code = fund_code

    def __str__(self):
        return (f"TradeResult("
            f"busin_serial_no={self.busin_serial_no}, "
            f"business_type={self.business_type}, "
            f"apply_work_day={self.apply_work_day}, "
            f"amount={self.amount}, "
            f"status={self.status}, "
            f"show_com_prop={self.show_com_prop}, "
            f"fund_code={self.fund_code})")