这个算法是用来 payload 传过来的组合 + 基金进行定向网格

payload 格式（止盈场景示例）：
{
  "account": "13918199137",
  "password": "sWX15706",
  "sub_account_name": "海外基金组合",
  "fund_list": [
    {
      "fund_code": "021539",
      "fund_name": "华安法国CAC40ETF发起式联接(QDII)A",
      "amount": 10000.0
    },
    {
      "fund_code": "017204",
      "fund_name": "华宝海外科技股票(QDII-LOF)C",
      "amount": 8000.0
    },
    {
      "fund_code": "016453",
      "fund_name": "南方纳斯达克100指数发起(QDII)C",
      "amount": 6000.0
    }
  ]
}

说明：
- 服务层会用 `times = asset_value // amount` 进行投资次数估算。
- 若某基金缺少 `amount` 或值无效，则该基金会被跳过，不执行止盈。
