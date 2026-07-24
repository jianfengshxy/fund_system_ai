class TradeResult:
    """
    单条交易记录的领域模型。

    该对象可由两个不同的 API 构造，注意字段值可能不同：

      get_one_fund_tran_infos (GetOneFundTranInfos API):
        - business_type: "买入" | "定投" | "卖基金回活期宝"
        - colour: "3"=已确认 | "4"=已撤单  (✅ 最可靠的撤单判断)
        - product_code / product_name: 可能为 None

      get_trades_list (GetQueryInfosQuickUse API):
        - business_type: "活期宝转入基金" | "活期宝转入定投" | "卖出回活期宝"
        - colour: ⚠️ 始终为 None
        - product_code / product_name: 有值

    交易有效性判断（已验证）:
      ⚠️ statu_icon == "3" 不代表交易成功！已撤单交易的 StatuIcon 也是 "3"。
      正确做法: 检查 app_state_text 是否含 "撤单"，或 colour == "4"（仅 GetOneFundTranInfos 可用）。

      business_code 含义（两个 API 一致）:
        22  = 买入 (活期宝转入基金)
        39  = 定投
        890 = 卖出 (卖出回活期宝)

    金额解析:
      confirm_count: 格式如 "5,000.00元" 或 "--"（交易未确认）
      apply_count:   格式如 "5,000.00元" 或 "942.77份"

      ⚠️ 买入交易在 colour=="4"(已撤单) 时，ConfirmCount 可能已有金额值（已支付但未最终成功），
         必须用 app_state_text 或 colour 过滤后再解析。
    """

    def __init__(
        self,
        busin_serial_no=None,
        business_type=None,       # 交易类型字符串，值取决于调用方 API（见类文档）
        apply_workday=None,
        apply_amount=None,
        status=None,              # ⚠️ 派生自 StatuIcon，"3" 不区分已确认和已撤单
        show_com_prop=None,
        fund_code=None,
        product_code=None,        # 基金代码（product_code 的备用字段）
        org_fund_code=None,
        org_fund_name=None,
        strike_start_date=None,  # 交易发起时间 "YYYY-MM-DD HH:MM:SS"
        cash_bag_app_time=None,
        product_name=None,
        business_code=None,      # 业务代码（22/39/890，两个 API 一致）
        display_business_code=None,
        apply_count=None,        # 申请金额/份额 (字符串，如 "5,000.00元")
        confirm_count=None,      # 确认金额/份额 (字符串，如 "5,000.00元" 或 "--")
        business_icon=None,
        statu_icon=None,         # "1"=受理中 | "3"=处理完成(含撤单！)
        remark=None,
        remark_url=None,
        colour=None,             # ⚠️ GetOneFundTranInfos: "3"=确认/"4"=撤单; GetQueryInfosQuickUse: None
        strategy_name=None,
        org_strategy_name=None,
        reference=None,
        busin_remark=None,
        id=None,
        app_state_text=None,     # "成功" | "已受理(支付完成)" | "已撤单(已支付)" | "已撤单" — 最可靠的撤单判断
        is_stay_on_way=None,
        sub_account_no=None,
        sub_account_name=None,
        raw=None,                 # 原始 API 响应 dict，含所有未映射字段
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
        self.sub_account_no = sub_account_no
        self.sub_account_name = sub_account_name

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
            status=item.get("status") or item.get("Status") or str(item.get("StatuIcon")),
            show_com_prop=item.get("show_com_prop") or item.get("ShowComProp"),
            fund_code=item.get("fund_code") or item.get("ProductCode"),

            # 新字段（全部保存）
            product_code=item.get("ProductCode"),
            org_fund_code=item.get("OrgFundCode"),
            org_fund_name=item.get("OrgFundName"),
            strike_start_date=item.get("StrikeStartDate"),
            cash_bag_app_time=item.get("CashBagAppTime"),
            product_name=item.get("ProductName"),
            business_code=item.get("BusinessCode"),
            display_business_code=item.get("DisplayBusinessCode"),
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
            sub_account_no=item.get("sub_account_no") or item.get("SubAccountNo"),
            sub_account_name=item.get("sub_account_name") or item.get("SubAccountName"),
            raw=item,
        )

    def __str__(self):
        return (f"TradeResult("
            f"id={self.id}, "
            f"code={self.fund_code}, "
            f"type={self.business_type}, "
            f"biz_code={self.business_code}, "
            f"date={self.strike_start_date}, "
            f"status={self.status}, "
            f"icon={self.statu_icon}, "
            f"colour={self.colour}, "
            f"state_text={self.app_state_text}, "
            f"confirm={self.confirm_count}, "
            f"apply={self.apply_count})")


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