import logging
import sys
import os
from flask import Flask, render_template, request, jsonify

# 将项目根目录和src目录添加到sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'src'))

from src.common.constant import DEFAULT_USER
from src.API.组合管理.SubAccountMrg import getSubAccountList
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.基金信息.FundInfo import getFundInfo, updateFundEstimatedValue
from src.domain.fund.fund_info import FundInfo

# 初始化 Flask 应用
app = Flask(__name__, template_folder='templates')

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@app.route('/', methods=['GET'])
def home():
    try:
        # 1. 获取所有组合列表
        sub_accounts_response = getSubAccountList(DEFAULT_USER)
        if not sub_accounts_response.Success or not sub_accounts_response.Data:
            return "获取组合列表失败", 500

        all_portfolios = sorted(sub_accounts_response.Data, key=lambda x: x.asset_value, reverse=True)
        top_5_portfolios = all_portfolios[:10]

        # 2. 确定默认选择的组合
        selected_portfolio_name = ''
        if top_5_portfolios:
            selected_portfolio_name = top_5_portfolios[0].sub_account_name

        return render_template('index.html',
                               portfolios=top_5_portfolios,
                               selected_portfolio_name=selected_portfolio_name)

    except Exception as e:
        logging.error(f"处理主页请求时发生错误: {e}", exc_info=True)
        return f"服务器内部错误: {e}", 500

@app.route('/api/portfolio/<portfolio_name>', methods=['GET'])
def get_portfolio_details(portfolio_name):
    try:
        total_assets = 0
        total_profit = 0
        estimated_portfolio_change_ratio = 0
        total_profit_value = 0
        portfolio_details = []
        
        # 获取组合信息以获取 constant_profit 和 profit_value
        sub_accounts_response = getSubAccountList(DEFAULT_USER)
        selected_portfolio = None
        if sub_accounts_response.Success and sub_accounts_response.Data:
            for portfolio in sub_accounts_response.Data:
                if portfolio.sub_account_name == portfolio_name:
                    selected_portfolio = portfolio
                    break

        # 获取所选组合的资产详情
        asset_details_list = get_sub_account_asset_by_name(DEFAULT_USER, portfolio_name)
        
        if asset_details_list:
            enriched_asset_details = []
            for asset in asset_details_list:
                total_assets += asset.asset_value
                total_profit += asset.hold_profit
                total_profit_value += asset.profit_value
                
                # 获取基金的今日估值
                fund_info = getFundInfo(DEFAULT_USER, asset.fund_code)
                if fund_info:
                    updated_fund_info = updateFundEstimatedValue(fund_info)
                    asset.estimated_change = updated_fund_info.estimated_change if updated_fund_info else 0.0
                else:
                    asset.estimated_change = 0.0
                enriched_asset_details.append(asset.to_dict()) # 假设 asset 对象有 to_dict 方法
            
            portfolio_details = enriched_asset_details

            # 计算组合整体数据
            if total_assets > 0:
                # 计算组合今日预估涨跌幅
                for asset in asset_details_list: # 使用原始对象列表
                    asset_weight = asset.asset_value / total_assets
                    estimated_portfolio_change_ratio += asset_weight * asset.estimated_change

        return jsonify({
            'portfolio_details': portfolio_details,
            'total_assets': total_assets,
            'total_profit': total_profit,
            'estimated_portfolio_change_ratio': estimated_portfolio_change_ratio,
            'total_profit_value': total_profit_value,
            'constant_profit': selected_portfolio.constant_profit if selected_portfolio else 0.0,
            'profit_value': selected_portfolio.profit_value if selected_portfolio else 0.0
        })

    except Exception as e:
        logging.error(f"获取组合详情时发生错误: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

# 函数计算的入口
def handler(environ, start_response):
    return app(environ, start_response)

if __name__ == "__main__":
    # 监听所有网卡，在同一局域网内可用
    app.run(host="0.0.0.0", port=9000, debug=True)