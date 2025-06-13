#!/usr/bin/env python3
import sys
sys.path.append('/Users/m672372/Documents/fund_system_ai/src')

from domain.fund.fund_investment_indicator import FundInvestmentIndicator

test_data = {'SHORTNAME': 'TestABC', 'FCODE': '123'}
result = FundInvestmentIndicator.from_dict(test_data)
print('Result:', result.fund_name)
print('Expected: Test (without ABC)')
print('Success:', 'ABC' not in result.fund_name)