import logging
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
_executor = ThreadPoolExecutor(max_workers=8)
_cache = {}

def _get_sub_accounts_cached():
    k = 'sub_accounts'
    v = _cache.get(k)
    if v and v[0] > time.time() - 30:
        return v[1]
    resp = getSubAccountList(DEFAULT_USER)
    _cache[k] = (time.time(), resp)
    return resp

def _get_assets_cached(portfolio_name):
    k = f'assets:{portfolio_name}'
    v = _cache.get(k)
    if v and v[0] > time.time() - 30:
        return v[1]
    lst = get_sub_account_asset_by_name(DEFAULT_USER, portfolio_name)
    _cache[k] = (time.time(), lst)
    return lst

@app.route('/', methods=['GET'])
def home():
    try:
        sub_accounts_response = _get_sub_accounts_cached()
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
        sub_accounts_response = _get_sub_accounts_cached()
        selected_portfolio = None
        if sub_accounts_response.Success and sub_accounts_response.Data:
            for portfolio in sub_accounts_response.Data:
                if portfolio.sub_account_name == portfolio_name:
                    selected_portfolio = portfolio
                    break

        asset_details_list = _get_assets_cached(portfolio_name) or []
        
        if asset_details_list:
            def _enrich(a):
                fi = getFundInfo(DEFAULT_USER, a.fund_code)
                if fi:
                    ufi = updateFundEstimatedValue(fi)
                    a.estimated_change = ufi.estimated_change if ufi else 0.0
                else:
                    a.estimated_change = 0.0
                return a

            futures = [_executor.submit(_enrich, a) for a in asset_details_list]
            enriched = []
            for f in as_completed(futures):
                a = f.result()
                enriched.append(a)
            for a in enriched:
                total_assets += a.asset_value
                total_profit += a.hold_profit
                total_profit_value += a.profit_value
            if total_assets > 0:
                for a in enriched:
                    w = a.asset_value / total_assets
                    estimated_portfolio_change_ratio += w * a.estimated_change
            portfolio_details = [a.to_dict() for a in enriched]

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


if __name__ == '__main__':
    # 为了本地测试，需要确保 templates 文件夹存在
    if not os.path.exists('templates'):
        os.makedirs('templates')
    # 创建一个临时的 index.html 以便本地运行
    if not os.path.exists('templates/index.html'):
        with open('templates/index.html', 'w') as f:
            f.write('<html><body><h1>请填充模板内容</h1></body></html>')
            
    app.run(debug=True, port=9000)
