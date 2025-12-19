
import sys
import os

# Adjust path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.domain.fund.fund_info import FundInfo

def test_fund_info_logic():
    print("Testing FundInfo logic...")
    
    # Case 1: Normal Open Fund
    data_buy_redeem = {'ISBUY': '1', 'FCODE': '111', 'SHORTNAME': 'Test1', 'NAV': '1.0', 'ACCNAV': '1.0', 'NAVCHGRT': '0.1'}
    info1 = FundInfo.from_dict(data_buy_redeem)
    print(f"ISBUY='1': Can Purchase={info1.can_purchase}, Can Redeem={info1.can_redeem}")
    assert info1.can_purchase == True
    assert info1.can_redeem == True

    # Case 2: Redeem Only (Paused Purchase) - The case user mentioned
    data_redeem_only = {'ISBUY': '4', 'FCODE': '222', 'SHORTNAME': 'Test2', 'NAV': '1.0', 'ACCNAV': '1.0', 'NAVCHGRT': '0.1'}
    info2 = FundInfo.from_dict(data_redeem_only)
    print(f"ISBUY='4': Can Purchase={info2.can_purchase}, Can Redeem={info2.can_redeem}")
    assert info2.can_purchase == False
    assert info2.can_redeem == True

    # Case 3: Closed
    data_closed = {'ISBUY': '0', 'FCODE': '333', 'SHORTNAME': 'Test3', 'NAV': '1.0', 'ACCNAV': '1.0', 'NAVCHGRT': '0.1'}
    info3 = FundInfo.from_dict(data_closed)
    print(f"ISBUY='0': Can Purchase={info3.can_purchase}, Can Redeem={info3.can_redeem}")
    assert info3.can_purchase == False
    assert info3.can_redeem == False

    print("All assertions passed!")

if __name__ == "__main__":
    test_fund_info_logic()
