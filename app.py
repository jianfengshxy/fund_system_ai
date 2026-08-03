import logging
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

# 将项目根目录和src目录添加到sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(root_dir)
sys.path.append(os.path.join(root_dir, 'src'))

from src.common.constant import DEFAULT_USER
from src.domain.user import ApiResponse
from src.API.组合管理.SubAccountMrg import getSubAccountList, getSubAssetMultList
from src.domain.sub_account.sub_account import SubAccount
from src.service.资产管理.get_fund_asset_detail import get_sub_account_asset_by_name
from src.API.基金信息.FundInfo import getFundInfo, updateFundEstimatedValue
from src.API.基金信息.FundRank import get_fund_volatility, get_nav_rank
from src.domain.fund.fund_info import FundInfo
from src.API.登录接口.login import ensure_user_fresh

# 初始化 Flask 应用
app = Flask(__name__, static_folder='static', static_url_path='')
CORS(app)  # 开启跨域支持，允许 Vue 前端访问 API

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
_executor = ThreadPoolExecutor(max_workers=8)
_cache = {}

def _get_sub_accounts_cached():
    k = 'sub_accounts'
    v = _cache.get(k)
    if v and v[0] > time.time() - 30:
        return v[1]
    u = ensure_user_fresh(DEFAULT_USER, 600)
    resp = getSubAccountList(u)
    try:
        if (not getattr(resp, 'Success', False)) or (not getattr(resp, 'Data', None)):
            err = str(getattr(resp, 'FirstError', '') or '')
            need_refresh = any(k in err for k in ['Token', 'token', '凭证', 'passport', '未登录', '请登录', 'UToken', 'CToken', 'passportid', '权限'])
            if need_refresh:
                u2 = ensure_user_fresh(u, 600, True)
                resp = getSubAccountList(u2)
        if (not getattr(resp, 'Success', False))     or (not getattr(resp, 'Data', None)):
            u_fallback = 'u2' in locals() and u2 or u
            fallback = getSubAssetMultList(u_fallback)
            if getattr(fallback, 'Success', False) and getattr(fallback, 'Data', None):
                groups = getattr(fallback.Data, 'list_group', []) or []
                lst = []
                for g in groups:
                    sa = SubAccount.from_basic_info(u_fallback.customer_no, getattr(g, 'sub_account_no', ''), getattr(g, 'group_name', ''))
                    try:
                        sa.asset_value = float(getattr(g, 'total_amount_decimal', 0.0) or 0.0)
                    except Exception:
                        sa.asset_value = 0.0
                    lst.append(sa)
                resp = ApiResponse(True, 0, lst, None, None)
            else:
                resp = ApiResponse(True, 0, [], None, None)
    except Exception:
        resp = ApiResponse(True, 0, [], None, None)
    _cache[k] = (time.time(), resp)
    return resp

def _get_assets_cached(portfolio_name):
    k = f'assets:{portfolio_name}'
    v = _cache.get(k)
    if v and v[0] > time.time() - 30:
        return v[1]
    u = ensure_user_fresh(DEFAULT_USER, 600)
    lst = get_sub_account_asset_by_name(u, portfolio_name)
    _cache[k] = (time.time(), lst)
    return lst

@app.route('/', methods=['GET'])
def index():
    return app.send_static_file('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'message': 'Fund System Backend API is running'})

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
                    # 场内基金 (type='a') 估值不可靠，直接设为 0.0；
                    # 其余基金（含 QDII/指数型）走统一估值入口，无重仓股估值时回退跟踪指数估算
                    if hasattr(fi, 'fund_type') and fi.fund_type == 'a':
                        a.estimated_change = 0.0
                    else:
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

@app.route('/api/cache/clear', methods=['POST'])
def clear_api_cache():
    _cache.clear()
    return jsonify({'success': True})

@app.route('/api/portfolios', methods=['GET'])
def get_portfolios_api():
    try:
        sub_accounts_response = _get_sub_accounts_cached()
        portfolios = []
        data = getattr(sub_accounts_response, 'Data', None)
        if isinstance(data, list):
            # 过滤掉资产为 0 的组合
            active_data = [p for p in data if (getattr(p, 'asset_value', 0.0) or 0.0) > 0]
            # 按资产价值降序排列
            sorted_data = sorted(active_data, key=lambda x: getattr(x, 'asset_value', 0.0) or 0.0, reverse=True)
            portfolios = [
                {
                    'sub_account_name': p.sub_account_name,
                    'asset_value': getattr(p, 'asset_value', 0.0) or 0.0
                } for p in sorted_data
            ]
        return jsonify({
            'portfolios': portfolios,
            'selected_portfolio_name': portfolios[0]['sub_account_name'] if portfolios else ''
        })
    except Exception as e:
        logging.error(f"获取组合列表失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/fund/<fund_code>', methods=['GET'])
def get_fund_detail_api(fund_code):
    try:
        user = ensure_user_fresh(DEFAULT_USER, 600)
        fi = getFundInfo(user, fund_code)
        if not fi:
            return jsonify({'error': '未找到基金信息'}), 404
        
        # 获取实时估值信息（场内基金 type='a' 估值不可靠，跳过；QDII/指数型走统一估值入口）
        if not (hasattr(fi, 'fund_type') and fi.fund_type == 'a'):
            updateFundEstimatedValue(fi)
        
        # 计算 5 日均值和波动率
        # 使用最近 5 个交易日的历史数据
        vol_data = get_fund_volatility(user, fi, 5)
        if vol_data:
            mean, variance, volatility = vol_data
            fi.nav_5day_avg = mean
            fi.volatility = volatility
        
        # 计算 30 日排名和 100 日排名
        fi.rank_30day = get_nav_rank(user, fi, 30)
        fi.rank_100day = get_nav_rank(user, fi, 100)
        
        # 将 FundInfo 对象转换为字典
        detail = {}
        for key in dir(fi):
            if not key.startswith('_') and not callable(getattr(fi, key)):
                value = getattr(fi, key)
                # 处理一些特殊类型
                if isinstance(value, (int, float, str, bool, list, dict)) or value is None:
                    detail[key] = value
                else:
                    detail[key] = str(value)
                    
        return jsonify(detail)
    except Exception as e:
        logging.error(f"获取基金详情失败: {e}", exc_info=True)
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
            
    # 开启 debug=True 方便本地开发自动重载
    app.run(host='0.0.0.0', port=9000, debug=True)
