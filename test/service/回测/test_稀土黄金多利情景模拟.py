#!/usr/bin/env python3
"""
稀土 011036 黄金多利情景模拟。

口径：
1. 以当前持仓状态为起点：
   - 本金 24,000
   - 当前收益率 -4.95%
2. 严格按黄金多利加仓逻辑拆成两条路径：
   - 路径A：继续下跌，没有反弹信号
   - 路径B：深跌后出现反弹信号（周/月转正且站上MA5）
3. 单基金上限按定投计划任务配置：50,000
"""

from dataclasses import dataclass


CURRENT_COST = 24000.0
CURRENT_PROFIT_RATE = -4.95
BASE_AMOUNT = 2000.0
FUND_LIMIT = 50000.0


@dataclass
class PositionState:
    cost: float
    nav_cost: float

    @property
    def shares(self) -> float:
        return self.cost / self.nav_cost

    def asset_value(self, nav_now: float) -> float:
        return self.shares * nav_now

    def profit_rate(self, nav_now: float) -> float:
        return (self.asset_value(nav_now) - self.cost) / self.cost * 100.0

    def buy(self, amount: float, nav_now: float) -> None:
        new_cost = self.cost + amount
        new_shares = self.shares + amount / nav_now
        self.cost = new_cost
        self.nav_cost = new_cost / new_shares


def fmt_money(value: float) -> str:
    return f"{value:,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def make_initial_state() -> tuple[PositionState, float]:
    nav_cost = 1.0
    nav_now = nav_cost * (1 + CURRENT_PROFIT_RATE / 100.0)
    return PositionState(cost=CURRENT_COST, nav_cost=nav_cost), nav_now


def path_continue_down() -> None:
    state, nav_now = make_initial_state()
    print("路径A：继续下跌，无反弹信号")
    print("-" * 84)
    print(f"{'场景':<18}{'触发收益率':<14}{'黄金多利动作':<28}{'新增投入':<12}{'累计本金':<12}")
    print("-" * 84)

    scenarios = [
        ("当前附近运行", nav_now, "会触发 2x 加仓窗口"),
        ("再跌 1%", nav_now * 0.99, "进入 -5% 以下死区"),
        ("再跌 5%", nav_now * 0.95, "仍在死区"),
        ("再跌 10%", nav_now * 0.90, "仍在死区"),
        ("再跌 20%", nav_now * 0.80, "仍在死区"),
    ]

    for label, test_nav, note in scenarios:
        temp = PositionState(cost=state.cost, nav_cost=state.nav_cost)
        profit = temp.profit_rate(test_nav)
        add_amount = 0.0
        action = ""

        if -5.0 <= profit < -4.0:
            add_amount = min(BASE_AMOUNT * 2.0, FUND_LIMIT - temp.cost)
            action = "加仓 4000"
            if add_amount > 0:
                temp.buy(add_amount, test_nav)
        elif -4.0 <= profit < -1.0:
            add_amount = min(BASE_AMOUNT, FUND_LIMIT - temp.cost)
            action = "加仓 2000"
            if add_amount > 0:
                temp.buy(add_amount, test_nav)
        elif -10.0 <= profit < -5.0:
            action = "熔断，不买"
        elif profit < -10.0:
            action = "继续等反弹信号，不买"
        else:
            action = "不触发加仓"

        print(
            f"{label:<18}{fmt_pct(profit):<14}{(action + '，' + note):<28}"
            f"{fmt_money(add_amount):<12}{fmt_money(temp.cost):<12}"
        )

    print()


def path_rebound_after_deep_drawdown() -> None:
    state, nav_now = make_initial_state()
    print("路径B：深跌后出现反弹信号")
    print("-" * 84)
    print(f"{'场景':<18}{'触发收益率':<14}{'黄金多利动作':<28}{'新增投入':<12}{'累计本金':<12}{'摊薄后收益率':<14}")
    print("-" * 84)

    scenarios = [
        ("当前先补一笔", nav_now, True),
        ("到 -10% 附近反弹", 0.90, False),
        ("到 -15% 附近反弹", 0.85, False),
        ("到 -20% 附近反弹", 0.80, False),
    ]

    # 第一步：当前如果策略正好执行一次，会先加 4000
    current_label, current_nav, _ = scenarios[0]
    current_profit = state.profit_rate(current_nav)
    first_add = 0.0
    if -5.0 <= current_profit < -4.0:
        first_add = min(BASE_AMOUNT * 2.0, FUND_LIMIT - state.cost)
        if first_add > 0:
            state.buy(first_add, current_nav)
    print(
        f"{current_label:<18}{fmt_pct(current_profit):<14}{'加仓 4000':<28}"
        f"{fmt_money(first_add):<12}{fmt_money(state.cost):<12}{fmt_pct(state.profit_rate(current_nav)):<14}"
    )

    # 第二步：深跌后，如果真的出现反弹信号，固定按 2 倍基础金额加仓；
    # 一旦跌破 -10%，则直接停止抄底，避免继续消耗现金。
    for label, target_nav_cost_ratio, _ in scenarios[1:]:
        temp = PositionState(cost=state.cost, nav_cost=state.nav_cost)
        # 这里的 0.90 / 0.85 / 0.80 是“相对初始成本净值 1.0”的价格位置
        test_nav = target_nav_cost_ratio
        profit = temp.profit_rate(test_nav)

        if profit < -10.0:
            add_amount = 0.0
            action = "跌破 -10%，停止抄底"
        else:
            add_amount = min(BASE_AMOUNT * 2.0, FUND_LIMIT - temp.cost)
            action = "反弹确认后加仓 2x"
            if add_amount > 0:
                temp.buy(add_amount, test_nav)

        print(
            f"{label:<18}{fmt_pct(profit):<14}{action:<28}"
            f"{fmt_money(add_amount):<12}{fmt_money(temp.cost):<12}{fmt_pct(temp.profit_rate(test_nav)):<14}"
        )

    print()


def main() -> None:
    state, nav_now = make_initial_state()
    print("=" * 84)
    print("稀土 011036 (中证稀土产业 930598) 黄金多利情景推演")
    print("=" * 84)
    print(
        f"当前持仓: 本金={fmt_money(state.cost)}  当前收益率={fmt_pct(CURRENT_PROFIT_RATE)}  "
        f"当前浮亏={fmt_money(state.asset_value(nav_now) - state.cost)}"
    )
    print(
        f"策略参数: amount={fmt_money(BASE_AMOUNT)}  单基金上限={fmt_money(FUND_LIMIT)}"
    )
    print()
    path_continue_down()
    path_rebound_after_deep_drawdown()
    print("结论：")
    print("1. 你现在这笔稀土，若任务此刻运行，大概率先补 4,000。")
    print("2. 一旦跌破 -5%，黄金多利会进入死区，单边下跌时不会继续追。")
    print("3. 真正的大额补仓，要等跌深后出现反弹信号才会触发。")
    print("4. 按 50,000 上限测算，这只稀土的理论最大占资是 50,000。")


if __name__ == "__main__":
    main()
