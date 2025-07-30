#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主动型组合定投管理系统

功能:
1. 查询指定组合的定投计划
2. 获取组合资产信息
3. 根据预算和风控规则判断是否创建新计划
4. 提供定投建议
"""

import sys
import os
from time import sleep
from typing import List, Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from src.common.constant import DEFAULT_USER
from src.domain.user.User import User
from src.service.定投管理.定投查询.定投查询 import get_portfolio_plan_details
from src.service.大数据.加仓风向标服务 import process_fund_investment_indicators
from src.API.定投计划管理.SmartPlan import createPlanV3, getFundPlanList
from src.service.定投管理.智能定投.智能定投管理 import dissolve_period_smart_investment
from src.service.定投管理.组合定投.组合定投管理 import create_period_investment_by_group
# 用户配置列表
# 第一列：手机号 account
# 第二列：密码 password
# 第三列：支付密码
# 第四列：姓名
# 第五列：sub_account_name组合名称
# 第六列：budget 预算
user_list = [
    # ("13918797997","Zj951103","Zj951103","仇晓钰","最优止盈",1000000.0),
    ("13918199137", "sWX15706", "sWX15706", "施小雨", "低风险组合", 3000000.0)
]


def setup_logger_plan_by_group(user: User, sub_account_name: str, budget: float = 1000000.0,investment_amount:float = 10000.0):
    """
    主动型组合定投管理函数
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称
        budget: 预算金额，默认100万
    """
    print(f"开始处理用户 {user.customer_name or user.account} 的组合 '{sub_account_name}' 定投管理")
    print(f"预算金额: {budget:,.2f} 元")
    
    try:
        # 1. 找到指定组合定投计划
        print("步骤1: 查询组合定投计划...")
        
        # 延迟导入避免循环依赖
        try:
            portfolio_details = get_portfolio_plan_details(user)
            
            # 过滤指定组合名称的定投计划
            target_plans = []
            for detail in portfolio_details:
                if detail.rationPlan and hasattr(detail.rationPlan, 'subAccountName'):
                    if detail.rationPlan.subAccountName == sub_account_name:
                        target_plans.append(detail)
                        print(f"找到匹配的定投计划: 计划ID={detail.rationPlan.planId}, 组合名称={detail.rationPlan.subAccountName},基金名称={detail.rationPlan.fundName},基金代码={detail.rationPlan.fundCode}")
            
            if not target_plans:
                print(f"未找到组合 '{sub_account_name}' 的现有定投计划")
            else:
                print(f"找到 {len(target_plans)} 个相关定投计划")
                
        except Exception as e:
            print(f"查询定投计划时出错: {e}")
            target_plans = []
        
        # 2. 获取组合的资产信息
        print("步骤2: 获取组合资产信息...")
        
        current_asset_value = 0.0
        asset_details = []
        
        try:
            from src.API.组合管理.SubAccountMrg import getSubAssetMultList
            from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
            
            # 获取子账户资产列表
            sub_asset_response = getSubAssetMultList(user)
            if sub_asset_response.Success:
                # 查找目标组合的资产信息
                target_group = None
                if sub_asset_response.Data and sub_asset_response.Data.list_group:
                    for group in sub_asset_response.Data.list_group:
                        if group.group_name == sub_account_name:
                            target_group = group
                            break
                
                if target_group:
                    current_asset_value = float(target_group.total_amount or 0)
                    print(f"组合 '{sub_account_name}' 当前资产价值: {current_asset_value:,.2f} 元")
                    
                    try:
                        total_profit = float(target_group.total_profit or 0)
                        print(f"组合总收益: {total_profit:,.2f} 元")
                    except (ValueError, TypeError):
                        print(f"组合总收益: {target_group.total_profit or 0} 元")
                else:
                    print(f"未找到组合 '{sub_account_name}' 的资产信息")
                
                # 获取详细的资产信息
                asset_details = get_sub_account_asset_by_name(user, sub_account_name)
                if asset_details:
                    print(f"组合包含 {len(asset_details)} 只基金")
                    for i, asset in enumerate(asset_details[:5]):  # 只显示前5只基金
                        try:
                            asset_value = float(asset.asset_value or 0)
                            # 获取盈亏比例信息
                            profit_info = ""
                            if asset.constant_profit_rate is not None:
                                profit_rate = asset.constant_profit_rate * 100  # 转换为百分比
                                profit_info = f" (收益率: {profit_rate:+.2f}%)"
                            elif asset.hold_profit_rate is not None:
                                profit_rate = asset.hold_profit_rate * 100  # 转换为百分比
                                profit_info = f" (收益率: {profit_rate:+.2f}%)"
                            
                            print(f"  基金{i+1}: {asset.fund_name} ({asset.fund_code}) - 持有金额: {asset.asset_value} 元")
                        except (ValueError, TypeError):
                            print(f"  基金{i+1}: {asset.fund_name} ({asset.fund_code}) - 持有金额: {asset.asset_value} 元")
                    if len(asset_details) > 5:
                        print(f"  ... 还有 {len(asset_details) - 5} 只基金")
            else:
                print(f"获取子账户资产列表失败: {sub_asset_response.Message}")
                
        except Exception as e:
            print(f"获取资产信息时出错: {e}")
        
        # 3. 检查资产配置条件
        print("步骤3: 检查资产配置条件...")
        budget_threshold = budget * 2.0 
        print(f"预算阈值: {budget_threshold:,.2f} 元")
        
        # 计算剩余预算
        remaining_budget = budget - current_asset_value
        print(f"剩余可投资金额: {remaining_budget:,.2f} 元")
        
        if current_asset_value >= budget_threshold:
            print(f"⚠️  当前资产价值 {current_asset_value:,.2f} 元已超过预算的阈值 ({budget_threshold:,.2f} 元)")
            print("⚠️  根据风控规则，当前资产已接近预算上限")
            if remaining_budget <= 0:
                print("❌ 剩余预算不足，不建议创建新的定投计划")
                return
            else:
                print(f"💡 剩余预算: {remaining_budget:,.2f} 元，可以考虑小额定投")
        else:
            print(f"✅ 当前资产价值未超过预算阈值，可以考虑创建定投计划")
        
        # 4. 创建计划的建议
        print("步骤4: 定投计划建议...")
        
        # 调用加仓风向标函数，获取推荐基金
        print("获取加仓风向标数据...")
        indicators_response = process_fund_investment_indicators(user, page_size=20)
        if not indicators_response:
            print("❌ 获取加仓风向标数据失败")
            return
        
        # 检查返回的数据类型
        if hasattr(indicators_response, 'Data'):
            indicators_data = indicators_response.Data
        else:
            # 如果直接返回列表
            indicators_data = indicators_response
        
        print(f"获取到 {len(indicators_data)} 个加仓风向标基金")
        
        # 过滤出基金类型非'000'的基金（非指数基金）
        non_index_funds = []
        for indicator in indicators_data:
            fund_code = indicator.fund_code
            fund_name = indicator.fund_name
            fund_type = getattr(indicator, 'fund_type', None)
            
            if fund_type != '000':  # 过滤掉指数基金
                non_index_funds.append(indicator)
                print(f"  候选基金: {fund_name}({fund_code}) - 类型: {fund_type or '未知'}")
            else:
                print(f"  跳过指数基金: {fund_name}({fund_code}) - 类型: {fund_type}")
        
        if not non_index_funds:
            print("❌ 没有找到符合条件的非指数基金")
            return
        
        print(f"筛选出 {len(non_index_funds)} 个非指数基金")
        
        # 检查这些基金是否已经有定投计划
        print("检查基金是否已有定投计划...")
        recommended_funds = []
        
        for indicator in non_index_funds:
            fund_code = indicator.fund_code
            fund_name = indicator.fund_name
            
            # 检查该基金是否已有定投计划
            try:
                existing_plans = getFundPlanList(fund_code, user)
                has_existing_plan = False
                
                if existing_plans:
                    for plan in existing_plans:
                        if hasattr(plan, 'fund_code') and plan.fund_code == fund_code:
                            has_existing_plan = True
                            print(f"  跳过基金 {fund_name}({fund_code}): 已有定投计划")
                            break
                        # 也检查组合名称匹配
                        if hasattr(plan, 'sub_account_name') and plan.sub_account_name == sub_account_name:
                            has_existing_plan = True
                            print(f"  跳过基金 {fund_name}({fund_code}): 在组合{sub_account_name}中已有定投计划")
                            break
                
                if not has_existing_plan:
                    recommended_funds.append(indicator)
                    print(f"  推荐基金: {fund_name}({fund_code}) - 无现有定投计划")
                    
            except Exception as e:
                print(f"  警告: 检查基金 {fund_code} 定投计划时出错: {e}，假设无现有计划")
                recommended_funds.append(indicator)
        
        if not recommended_funds:
            print("✅ 所有符合条件的基金都已有定投计划，无需创建新计划")
        else:
            print(f"\n💡 建议为以下 {len(recommended_funds)} 个基金创建定投计划:")
            
            # 计算建议的定投金额
            suggested_monthly_amount = investment_amount  # 预算值除以200
            
            for i, indicator in enumerate(recommended_funds[:5], 1):  # 最多推荐5个基金
                fund_code = indicator.fund_code
                fund_name = indicator.fund_name
                print(f"  {i}. {fund_name}({fund_code}) - 建议月定投: {suggested_monthly_amount:,.0f} 元")
                
                # 自动创建定投计划
                try:
                    print(f"  🚀 正在为 {fund_name}({fund_code}) 创建定投计划，金额: {suggested_monthly_amount:,.0f} 元")
                    
                    # 调用创建定投计划API
                    period_type = 4  # 3=月定投, 4=日定投
                    response = create_period_investment_by_group(
                        user=user,
                        fund_code=fund_code,
                        amount=int(suggested_monthly_amount),  
                        period_type=period_type,
                        period_value=1,
                        sub_account_name=sub_account_name
                    )
                    sleep(10)
                    
                    # 检查返回值：None表示已存在定投计划，这是正常情况
                    if response is None:
                        print(f"  ℹ️  基金 {fund_name}({fund_code}) 在组合 '{sub_account_name}' 中已存在定投计划，跳过创建")
                    elif response and hasattr(response, 'Success') and response.Success:
                        if response.Data:
                            plan = response.Data
                            print(f"  ✅ 成功创建定投计划!")
                            print(f"     计划ID: {plan.planId}")
                            print(f"     基金名称: {plan.fundName}({plan.fundCode})")
                            print(f"     定投金额: {plan.amount} 元")
                            # 根据period_type显示正确的定投周期
                            period_desc = "月定投" if period_type == 3 else "日定投" if period_type == 4 else f"周期类型{period_type}"
                            print(f"     定投周期: {period_desc}")
                            print(f"     组合名称: {sub_account_name}")
                            print(f"     子账户编号: {plan.subAccountNo}")
                            print(f"     下次扣款日期: {plan.nextDeductDate}")
                        else:
                            print(f"  ❌ 创建定投计划失败: 响应数据为空")
                    else:
                        error_msg = "未知错误"
                        if response and hasattr(response, 'FirstError') and response.FirstError:
                            error_msg = response.FirstError
                        elif response and hasattr(response, 'DebugError') and response.DebugError:
                            error_msg = response.DebugError
                        print(f"  ❌ 创建定投计划失败: {error_msg}")
                        
                except Exception as e:
                    print(f"  ❌ 创建定投计划时发生异常: {str(e)}")
                    # 打印更详细的错误信息用于调试
                    import traceback
                    print(f"     详细错误信息: {traceback.format_exc()}")
        
        print(f"\n✅ 组合 '{sub_account_name}' 定投管理分析完成")
        
    except Exception as e:
        print(f"❌ 处理组合定投管理时发生错误: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")


def create_plan_by_group(user: User, sub_account_name: str, budget: float, investment_amount: float):
    """
    为指定组合创建定投计划
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称
        budget: 预算金额
    """
    print(f"🚀 开始为组合 '{sub_account_name}' 创建定投计划，预算: {budget:,.2f} 元")
    
    # 调用主要的分析函数
    setup_logger_plan_by_group(user, sub_account_name, budget,investment_amount)


def batch_process_users():
    """
    批量处理用户列表中的组合定投管理
    """
    print("🔄 开始批量处理用户组合定投管理")
    
    for user_info in user_list:
        try:
            account, password, paypassword, name, sub_account_name, budget = user_info
            
            # 创建用户对象
            user = User(account, password, paypassword)
            user.customer_name = name
            
            print(f"\n{'='*60}")
            print(f"处理用户: {name} ({account})")
            print(f"{'='*60}")
            
            # 执行组合定投管理
            create_plan_by_group(user, sub_account_name, budget,1000.0)
            
        except Exception as e:
            print(f"❌ 处理用户 {user_info} 时发生错误: {str(e)}")
            continue
    
    print("\n✅ 批量处理完成")


def main():
    """
    主程序入口
    """
    print("🎯 主动型组合定投管理系统启动")
    
    # 可以选择单个用户测试或批量处理
    import argparse
    
    parser = argparse.ArgumentParser(description='主动型组合定投管理')
    parser.add_argument('--batch', action='store_true', help='批量处理所有用户')
    parser.add_argument('--user', type=str, help='指定用户手机号')
    parser.add_argument('--account', type=str, help='指定组合名称')
    
    args = parser.parse_args()
    
    if args.batch:
        # 批量处理
        batch_process_users()
    elif args.user and args.account:
        # 单个用户处理
        user_info = None
        for info in user_list:
            if info[0] == args.user:
                user_info = info
                break
        
        if user_info:
            account, password, paypassword, name, _, budget = user_info
            user = User(account, password, paypassword)
            user.customer_name = name
            create_plan_by_group(user, args.account, budget,1000.0)
        else:
            print(f"❌ 未找到用户 {args.user}")
    else:
        # 默认处理第一个用户
        if user_list:
            account, password, paypassword, name, sub_account_name, budget = user_list[0]
            user = User(account, password, paypassword)
            user.customer_name = name
            
            print("🧪 使用默认用户进行测试")
            create_plan_by_group(user, sub_account_name, budget,1000.0)
        else:
            print("❌ 用户列表为空")
    
    print("\n🏁 程序执行完成")


def dissolve_plan_by_group(user: User, sub_account_name: str, budget: float):
    """
    解散指定组合的符合条件的定投计划
    
    Args:
        user: 用户对象
        sub_account_name: 组合名称
        budget: 预算金额
    """
    print(f"🔄 开始解散组合 '{sub_account_name}' 的定投计划，预算: {budget:,.2f} 元")
    
    try:
        # 1. 找到指定组合定投计划
        print("步骤1: 查询组合定投计划...")
        
        try:
            portfolio_details = get_portfolio_plan_details(user)
            
            # 过滤指定组合名称的定投计划
            target_plans = []
            for detail in portfolio_details:
                if detail.rationPlan and hasattr(detail.rationPlan, 'subAccountName'):
                    if detail.rationPlan.subAccountName == sub_account_name:
                        target_plans.append(detail)
                        print(f"找到定投计划: 计划ID={detail.rationPlan.planId}, 基金={detail.rationPlan.fundName}({detail.rationPlan.fundCode})")
            
            if not target_plans:
                print(f"未找到组合 '{sub_account_name}' 的定投计划")
                return
            else:
                print(f"找到 {len(target_plans)} 个定投计划")
                
        except Exception as e:
            print(f"查询定投计划时出错: {e}")
            return
        
        # 2. 获取组合的资产信息
        print("步骤2: 获取组合资产信息...")
        
        current_asset_value = 0.0
        asset_details = []
        
        try:
            from src.API.组合管理.SubAccountMrg import getSubAssetMultList
            from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
            
            # 获取子账户资产列表
            sub_asset_response = getSubAssetMultList(user)
            if sub_asset_response.Success:
                # 查找目标组合的资产信息
                target_group = None
                if sub_asset_response.Data and sub_asset_response.Data.list_group:
                    for group in sub_asset_response.Data.list_group:
                        if group.group_name == sub_account_name:
                            target_group = group
                            break
                
                if target_group:
                    current_asset_value = float(target_group.total_amount or 0)
                    print(f"组合 '{sub_account_name}' 当前资产价值: {current_asset_value:,.2f} 元")
                    
                    # 获取详细的资产信息
                    asset_details = get_sub_account_asset_by_name(user, sub_account_name)
                    if asset_details:
                        print(f"组合包含 {len(asset_details)} 只基金")
                else:
                    print(f"未找到组合 '{sub_account_name}' 的资产信息")
                    
        except Exception as e:
            print(f"获取资产信息时出错: {e}")
        
        # 3. 检查资产配置条件(组合的总资产大于70%)
        print("步骤3: 检查资产配置条件...")
        budget_threshold = budget * 1.0  # 70%预算阈值
        print(f"预算阈值 (100%): {budget_threshold:,.2f} 元")
        
        if current_asset_value <= budget_threshold:
            print(f"✅ 当前资产价值 {current_asset_value:,.2f} 元未超过预算的100%，不需要解散定投计划")
            return
        else:
            print(f"⚠️  当前资产价值 {current_asset_value:,.2f} 元已超过预算的100% ({budget_threshold:,.2f} 元)")
            print("⚠️  根据风控规则，需要考虑解散部分定投计划")
        
        # 4. 找出加仓风向标里面的基金组合
        print("步骤4: 获取加仓风向标基金...")
        
        recommended_fund_codes = set()
        try:
            indicators_response = getFundInvestmentIndicators(user, page_size=20)
            if indicators_response:
                # 检查返回的数据类型
                if hasattr(indicators_response, 'Data'):
                    indicators_data = indicators_response.Data
                else:
                    indicators_data = indicators_response
                
                # 过滤出基金类型非'000'的基金（非指数基金）
                for indicator in indicators_data:
                    fund_type = getattr(indicator, 'fund_type', None)
                    if fund_type != '000':  # 过滤掉指数基金
                        recommended_fund_codes.add(indicator.fund_code)
                        print(f"  加仓风向标基金: {indicator.fund_name}({indicator.fund_code})")
                
                print(f"获取到 {len(recommended_fund_codes)} 个加仓风向标基金")
            else:
                print("❌ 获取加仓风向标数据失败")
                
        except Exception as e:
            print(f"获取加仓风向标时出错: {e}")
        
        # 5. 检查定投计划的基金，如果资金为0或者为空，且不在加仓风向标的基金中，则解散这个组合
        print("步骤5: 检查并解散符合条件的定投计划...")
        
        plans_to_dissolve = []
        
        for plan_detail in target_plans:
            plan = plan_detail.rationPlan
            fund_code = plan.fundCode
            fund_name = plan.fundName
            plan_id = plan.planId
            
            # 检查该基金的资产情况
            fund_asset_value = 0.0
            for asset in asset_details:
                if asset.fund_code == fund_code:
                    try:
                        fund_asset_value = float(asset.asset_value or 0)
                    except (ValueError, TypeError):
                        fund_asset_value = 0.0
                    break
            
            # 判断是否需要解散：资金为0或为空，且不在加仓风向标中
            should_dissolve = False
            reason = ""
            
            if fund_asset_value <= 0:
                if fund_code not in recommended_fund_codes:
                    should_dissolve = True
                    reason = f"资产为0且不在加仓风向标中"
                else:
                    reason = f"资产为0但在加仓风向标中，保留"
            else:
                if fund_code not in recommended_fund_codes:
                    reason = f"有资产({fund_asset_value:,.2f}元)但不在加仓风向标中，考虑解散"
                    # 可以根据具体业务规则决定是否解散有资产但不在风向标中的基金
                    # should_dissolve = True
                else:
                    reason = f"有资产({fund_asset_value:,.2f}元)且在加仓风向标中，保留"
            
            print(f"  基金 {fund_name}({fund_code}): {reason}")
            
            if should_dissolve:
                plans_to_dissolve.append({
                    'plan_id': plan_id,
                    'fund_code': fund_code,
                    'fund_name': fund_name,
                    'reason': reason
                })
        
        # 执行解散操作
        if not plans_to_dissolve:
            print("✅ 没有找到需要解散的定投计划")
        else:
            print(f"\n💡 准备解散以下 {len(plans_to_dissolve)} 个定投计划:")
                
            for plan_info in plans_to_dissolve:
                print(f"  🗑️  解散计划: {plan_info['fund_name']}({plan_info['fund_code']}) - {plan_info['reason']}")
                    
                try:
                        # 调用真实的解散定投计划API
                        plan_id = plan_info['plan_id']
                        fund_code = plan_info['fund_code']
                        fund_name = plan_info['fund_name']
                        
                        print(f"    📋 正在解散计划ID: {plan_id}")
                        result = dissolve_period_smart_investment(user, plan_id)
                        
                        if result and hasattr(result, 'Success') and result.success:
                            print(f"    ✅ 成功解散定投计划: {fund_name}({fund_code})")
                        else:
                            print(f"    ❌ 解散定投计划失败: {fund_name}({fund_code})")
                            if result and hasattr(result, 'message'):
                                print(f"       错误信息: {result.message}")
                        
                except Exception as e:
                        print(f"    ❌ 解散定投计划时发生异常: {str(e)}")
                        import traceback
                        print(f"       详细错误信息: {traceback.format_exc()}")
                
            print(f"\n✅ 组合 '{sub_account_name}' 定投计划解散分析完成")
        
    except Exception as e:
        print(f"❌ 处理组合定投计划解散时发生错误: {str(e)}")
        import traceback
        print(f"错误详情: {traceback.format_exc()}")

if __name__ == '__main__':
    create_plan_by_group(DEFAULT_USER,"低风险组合",1000000.0,10000.0)
    dissolve_plan_by_group(DEFAULT_USER,"低风险组合",1000000.0)