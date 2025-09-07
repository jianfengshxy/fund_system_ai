class TradeResult:
    def __init__(
        self,
        busin_serial_no=None,
        business_type=None,
        apply_workday=None,
        apply_amount=None,
        status=None,
        show_com_prop=None,
        fund_code=None,
        # 新增：responseObjects 中的全部字段（以下命名为下划线风格）
        product_code=None,
        org_fund_code=None,
        org_fund_name=None,
        strike_start_date=None,
        cash_bag_app_time=None,
        product_name=None,
        business_code=None,
        display_business_code=None,
        apply_count=None,
        confirm_count=None,
        business_icon=None,
        statu_icon=None,
        remark=None,
        remark_url=None,
        colour=None,
        strategy_name=None,
        org_strategy_name=None,
        reference=None,
        busin_remark=None,
        id=None,
        app_state_text=None,
        is_stay_on_way=None,
        # 预留原始对象
        raw=None,
    ):
        # 兼容历史字段
        self.busin_serial_no = busin_serial_no
        self.business_type = business_type
        self.apply_work_day = apply_workday
        self.amount = apply_amount
        self.status = status
        self.show_com_prop = show_com_prop
        self.fund_code = fund_code

        # 新增字段保存（全部保留）
        self.product_code = product_code
        self.org_fund_code = org_fund_code
        self.org_fund_name = org_fund_name
        self.strike_start_date = strike_start_date
        self.cash_bag_app_time = cash_bag_app_time
        self.product_name = product_name
        self.business_code = business_code
        self.display_business_code = display_business_code
        self.apply_count = apply_count
        self.confirm_count = confirm_count
        self.business_icon = business_icon
        self.statu_icon = statu_icon
        self.remark = remark
        self.remark_url = remark_url
        self.colour = colour
        self.strategy_name = strategy_name
        self.org_strategy_name = org_strategy_name
        self.reference = reference
        self.busin_remark = busin_remark
        self.id = id
        self.app_state_text = app_state_text
        self.is_stay_on_way = is_stay_on_way

        # 兜底映射，保证旧字段尽量有值
        if self.fund_code is None and self.product_code is not None:
            self.fund_code = self.product_code
        if self.busin_serial_no is None and self.id is not None:
            # 对于查询类返回，没有 busin_serial_no，用 id 兜底便于日志使用
            self.busin_serial_no = self.id
        if self.business_type is None and self.product_name is not None:
            # 优先用 BusinessType，如果没传则不覆盖
            pass

        # 保留原始响应（可选）
        self.raw = raw

    @classmethod
    def from_api(cls, item: dict):
        """
        从单条交易记录字典构造 TradeResult。
        会把 API 字段名转换为类属性名，并保留原始 item 到 raw。
        """
        return cls(
            # 历史字段（若 API 不提供，可由新增字段兜底）
            busin_serial_no=item.get("busin_serial_no") or item.get("ID"),
            business_type=item.get("business_type") or item.get("BusinessType"),
            apply_workday=item.get("apply_workday") or item.get("StrikeStartDate"),
            apply_amount=item.get("apply_amount") or item.get("ApplyCount"),
            status=item.get("status"),
            show_com_prop=item.get("show_com_prop"),
            fund_code=item.get("fund_code") or item.get("ProductCode"),

            # 新字段（全部保存）
            product_code=item.get("ProductCode"),
            org_fund_code=item.get("OrgFundCode"),
            org_fund_name=item.get("OrgFundName"),
            strike_start_date=item.get("StrikeStartDate"),
            cash_bag_app_time=item.get("CashBagAppTime"),
            product_name=item.get("ProductName"),
            business_code=item.get("BusinessCode"),
            display_business_code=item.get("DisPlayBusinessCode"),
            apply_count=item.get("ApplyCount"),
            confirm_count=item.get("ConfirmCount"),
            business_icon=item.get("BusinessIcon"),
            statu_icon=item.get("StatuIcon"),
            remark=item.get("Remark"),
            remark_url=item.get("RemarkURL"),
            colour=item.get("Colour"),
            strategy_name=item.get("StrategyName"),
            org_strategy_name=item.get("OrgStrategyName"),
            reference=item.get("Reference"),
            busin_remark=item.get("BusinRemark"),
            id=item.get("ID"),
            app_state_text=item.get("APPStateText"),
            is_stay_on_way=item.get("IsStayOnWay"),
            raw=item,
        )

    def __str__(self):
        return (f"TradeResult("
            f"busin_serial_no={self.busin_serial_no}, "
            f"business_type={self.business_type}, "
            f"apply_work_day={self.apply_work_day}, "
            f"amount={self.amount}, "
            f"status={self.status}, "
            f"show_com_prop={self.show_com_prop}, "
            f"fund_code={self.fund_code})")


class TradeQueryResponse:
    """
    顶层交易查询返回的封装，保存所有元信息，并将 responseObjects 映射为 TradeResult 列表。
    """
    def __init__(
        self,
        succeed=None,
        pre_value=None,
        total_count=None,
        error_message=None,
        code_message=None,
        error_code=None,
        old_message=None,
        trace_identifier=None,
        error_msg_lst=None,
        err_pass_count=None,
        response_objects=None,
        raw=None,
    ):
        self.succeed = succeed
        self.pre_value = pre_value
        self.total_count = total_count
        self.error_message = error_message
        self.code_message = code_message
        self.error_code = error_code
        self.old_message = old_message
        self.trace_identifier = trace_identifier
        self.error_msg_lst = error_msg_lst
        self.err_pass_count = err_pass_count
        self.response_objects = response_objects or []
        self.raw = raw

    @classmethod
    def from_api_response(cls, resp: dict):
        ros = resp.get("responseObjects") or []
        results = [TradeResult.from_api(item) for item in ros]
        return cls(
            succeed=resp.get("Succeed"),
            pre_value=resp.get("PreValue"),
            total_count=resp.get("TotalCount"),
            error_message=resp.get("ErrorMessage"),
            code_message=resp.get("CodeMessage"),
            error_code=resp.get("ErrorCode"),
            old_message=resp.get("OldMessage"),
            trace_identifier=resp.get("TraceIdentifier"),
            error_msg_lst=resp.get("ErrorMsgLst"),
            err_pass_count=resp.get("ErrPassCount"),
            response_objects=results,
            raw=resp,
        )