export type MockPortfolioItem = {
  sub_account_name: string
  asset_value: number
}

export type MockAssetDetail = {
  fund_name: string
  fund_code: string
  asset_value: number
  constant_profit: number
  constant_profit_rate: number
  estimated_change: number
}

export const mockPortfoliosResponse: {
  portfolios: MockPortfolioItem[]
  selected_portfolio_name: string
} = {
  portfolios: [
    { sub_account_name: '海外基金组合', asset_value: 356_820.35 },
    { sub_account_name: '快速止盈', asset_value: 128_450.12 },
    { sub_account_name: '马丁格尔plus', asset_value: 512_030.77 }
  ],
  selected_portfolio_name: '海外基金组合'
}

const mockPortfolioDetailsByName: Record<string, MockAssetDetail[]> = {
  海外基金组合: [
    {
      fund_name: '广发纳斯达克100指数A',
      fund_code: '270042',
      asset_value: 124_580.22,
      constant_profit: 4_280.12,
      constant_profit_rate: 3.56,
      estimated_change: -0.48
    },
    {
      fund_name: '华夏恒生科技ETF联接A',
      fund_code: '012348',
      asset_value: 98_210.63,
      constant_profit: -1_820.55,
      constant_profit_rate: -1.82,
      estimated_change: 1.26
    },
    {
      fund_name: '易方达标普500ETF联接A',
      fund_code: '050025',
      asset_value: 134_029.50,
      constant_profit: 6_112.80,
      constant_profit_rate: 4.78,
      estimated_change: 0.32
    }
  ],
  快速止盈: [
    {
      fund_name: '中欧医疗健康混合A',
      fund_code: '003095',
      asset_value: 68_450.10,
      constant_profit: 980.21,
      constant_profit_rate: 1.45,
      estimated_change: -0.18
    },
    {
      fund_name: '景顺长城新兴成长混合',
      fund_code: '260108',
      asset_value: 59_999.99,
      constant_profit: -320.44,
      constant_profit_rate: -0.53,
      estimated_change: 0.64
    }
  ],
  马丁格尔plus: [
    {
      fund_name: '富国中证新能源ETF联接A',
      fund_code: '012857',
      asset_value: 210_300.33,
      constant_profit: -8_720.11,
      constant_profit_rate: -3.98,
      estimated_change: 1.92
    },
    {
      fund_name: '南方中证500ETF联接A',
      fund_code: '160119',
      asset_value: 301_730.44,
      constant_profit: 12_180.23,
      constant_profit_rate: 4.21,
      estimated_change: -0.73
    }
  ]
}

export const getMockPortfolioResponse = (name: string) => {
  const portfolio_details = mockPortfolioDetailsByName[name] ?? []
  const total_assets = portfolio_details.reduce((acc, cur) => acc + cur.asset_value, 0)
  const constant_profit = portfolio_details.reduce((acc, cur) => acc + cur.constant_profit, 0)
  const profit_value = constant_profit
  const estimated_portfolio_change_ratio =
    total_assets === 0
      ? 0
      : portfolio_details.reduce((acc, cur) => acc + (cur.asset_value * cur.estimated_change) / 100, 0) /
        (total_assets / 100)

  return {
    portfolio_details,
    total_assets,
    total_profit_value: constant_profit,
    estimated_portfolio_change_ratio,
    constant_profit,
    profit_value
  }
}

const mockFundDetailByCode: Record<string, Record<string, any>> = {
  '270042': {
    fund_name: '广发纳斯达克100指数A',
    fund_code: '270042',
    fund_type: 'QDII',
    fund_sub_type: '指数',
    index_code: 'NDX',
    nav: 1.8321,
    acc_nav: 2.4215,
    nav_date: '2026-07-10',
    nav_change: -0.35,
    estimated_value: 1.8233,
    estimated_change: -0.48,
    estimated_time: '2026-07-11 14:35:00',
    nav_5day_avg: 1.8452,
    week_return: 0.62,
    month_return: 3.15,
    three_month_return: 8.42,
    six_month_return: 12.33,
    this_year_return: 15.28,
    volatility: 18.6,
    rank_30day: 16,
    rank_100day: 38,
    can_purchase: true,
    can_redeem: true,
    max_purchase: 50000
  },
  '012348': {
    fund_name: '华夏恒生科技ETF联接A',
    fund_code: '012348',
    fund_type: 'QDII',
    fund_sub_type: '指数',
    index_code: 'HSTECH',
    nav: 0.7812,
    acc_nav: 0.9125,
    nav_date: '2026-07-10',
    nav_change: 0.48,
    estimated_value: 0.7911,
    estimated_change: 1.26,
    estimated_time: '2026-07-11 14:35:00',
    nav_30day_avg: 0.7725,
    week_return: -1.82,
    month_return: 2.11,
    three_month_return: 6.25,
    six_month_return: -4.33,
    this_year_return: 9.04,
    volatility: 22.1,
    rank_30day: 9,
    rank_100day: 44,
    can_purchase: true,
    can_redeem: true,
    max_purchase: 20000
  },
  '050025': {
    fund_name: '易方达标普500ETF联接A',
    fund_code: '050025',
    fund_type: 'QDII',
    fund_sub_type: '指数',
    index_code: 'SPX',
    nav: 2.1023,
    acc_nav: 2.9801,
    nav_date: '2026-07-10',
    nav_change: 0.12,
    estimated_value: 2.1090,
    estimated_change: 0.32,
    estimated_time: '2026-07-11 14:35:00',
    nav_30day_avg: 2.0952,
    week_return: 0.88,
    month_return: 1.62,
    three_month_return: 5.33,
    six_month_return: 9.18,
    this_year_return: 11.05,
    volatility: 14.4,
    rank_30day: 22,
    rank_100day: 41,
    can_purchase: true,
    can_redeem: true,
    max_purchase: 100000
  }
}

export const getMockFundDetail = (fundCode: string) => {
  return mockFundDetailByCode[fundCode] ?? { fund_code: fundCode, fund_name: '未知基金' }
}

