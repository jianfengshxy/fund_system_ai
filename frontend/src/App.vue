<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import axios from 'axios'
import { Menu, Refresh, Setting, UserFilled } from '@element-plus/icons-vue'

// 配置生产环境 API 地址
axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || ''

interface AssetDetail {
  fund_name: string
  fund_code: string
  asset_value: number
  hold_profit: number
  constant_profit_rate: number
  estimated_change: number
  profit_value: number
  [key: string]: any
}

interface Portfolio {
  sub_account_name: string
  asset_value: number
}

const portfolios = ref<Portfolio[]>([])
const selectedPortfolioName = ref('')
const portfolioDetails = ref<AssetDetail[]>([])
const totalAssets = ref(0)
const totalProfit = ref(0)
const totalProfitValue = ref(0)
const estimatedChangeRatio = ref(0)
const constantProfit = ref(0)
const profitValue = ref(0)
const loading = ref(false)
const tableLoading = ref(false)
const isCollapse = ref(false)
const detailDialogVisible = ref(false)
const selectedFundDetail = ref<any>(null)
const detailLoading = ref(false)

const fundFieldMap: Record<string, string> = {
  // 基础信息
  fund_name: '基金名称',
  fund_code: '基金代码',
  fund_type: '基金类型',
  fund_sub_type: '基金子类型',
  index_code: '指数代码',
  
  // 净值与估值
  nav: '当前净值',
  acc_nav: '累计净值',
  nav_date: '净值日期',
  nav_change: '净值涨跌幅',
  estimated_value: '估算净值',
  estimated_change: '估算涨跌幅',
  estimated_time: '估算时间',
  nav_5day_avg: '5日均值',
  
  // 收益率表现
  week_return: '周收益率',
  month_return: '近一月收益率',
  three_month_return: '3个月收益率',
  six_month_return: '6个月收益率',
  this_year_return: '今年以来收益率',
  
  // 风险与排名
  volatility: '波动率',
  rank_30day: '30日排名',
  rank_100day: '百日排名',
  
  // 交易状态
  can_purchase: '可买入',
  can_redeem: '可赎回',
  max_purchase: '单日限额',
  
  // 其他
  total_count: '总项数'
}

const fundFieldOrder = [
  'fund_name', 'fund_code', 'fund_type', 'fund_sub_type', 'index_code',
  'nav', 'acc_nav', 'nav_date', 'nav_change', 'estimated_value', 'estimated_change', 'estimated_time', 'nav_5day_avg',
  'week_return', 'month_return', 'three_month_return', 'six_month_return', 'this_year_return',
  'volatility', 'rank_30day', 'rank_100day',
  'can_purchase', 'can_redeem', 'max_purchase'
]

const showFundDetail = async (fundCode: string) => {
  detailDialogVisible.value = true
  detailLoading.value = true
  try {
    const res = await axios.get(`/api/fund/${fundCode}`)
    selectedFundDetail.value = res.data
  } catch (error) {
    console.error('Fetch fund detail error:', error)
  } finally {
    detailLoading.value = false
  }
}

const estProfitValue = computed(() => {
  return (estimatedChangeRatio.value * totalAssets.value) / 100
})

const fetchPortfolios = async () => {
  try {
    const res = await axios.get('/api/portfolios')
    portfolios.value = res.data.portfolios
    if (res.data.selected_portfolio_name && !selectedPortfolioName.value) {
      loadPortfolio(res.data.selected_portfolio_name)
    }
  } catch (error) {
    console.error('Fetch portfolios error:', error)
  }
}

const loadPortfolio = async (name: string) => {
  if (!name) return
  selectedPortfolioName.value = name
  tableLoading.value = true
  
  // 重置概览数据，避免切换时显示旧数据
  totalAssets.value = 0
  totalProfit.value = 0
  totalProfitValue.value = 0
  estimatedChangeRatio.value = 0
  constantProfit.value = 0
  profitValue.value = 0
  portfolioDetails.value = []

  try {
    const res = await axios.get(`/api/portfolio/${encodeURIComponent(name)}`)
    portfolioDetails.value = res.data.portfolio_details
    totalAssets.value = res.data.total_assets
    totalProfit.value = res.data.total_profit
    totalProfitValue.value = res.data.total_profit_value
    estimatedChangeRatio.value = res.data.estimated_portfolio_change_ratio
    constantProfit.value = res.data.constant_profit
    profitValue.value = res.data.profit_value
  } catch (error) {
    console.error('Load portfolio error:', error)
  } finally {
    tableLoading.value = false
  }
}

const formatNumber = (num: number) => {
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

const getStatusClass = (num: number) => {
  if (num > 0) return 'text-[#f5222d]' // 红色表示上涨
  if (num < 0) return 'text-[#52c41a]' // 绿色表示下跌
  return 'text-gray-700'
}

const getPrefix = (num: number) => {
  return num > 0 ? '+' : ''
}

onMounted(async () => {
  loading.value = true
  await fetchPortfolios()
  loading.value = false
})
</script>

<template>
  <el-container class="h-screen overflow-hidden">
    <el-header class="bg-brand text-white flex items-center justify-between px-4 h-14 shrink-0 shadow-md z-30">
      <div class="flex items-center gap-4">
        <el-button 
          link 
          class="text-white md:hidden" 
          @click="isCollapse = !isCollapse"
        >
          <el-icon :size="24"><Menu /></el-icon>
        </el-button>
        <div class="font-bold text-lg flex items-center gap-2">
          <el-icon><TrendCharts /></el-icon>
          <span class="hidden sm:inline">基金管理系统</span>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <el-tag type="info" effect="dark" class="hidden xs:inline-flex">生产环境</el-tag>
        <div class="flex items-center gap-2 cursor-pointer hover:bg-white/10 px-2 py-1 rounded transition">
          <el-avatar :size="28"><UserFilled /></el-avatar>
          <span class="hidden sm:inline">管理员</span>
        </div>
      </div>
    </el-header>

    <el-container class="overflow-hidden">
      <el-aside 
        :width="isCollapse ? '64px' : '260px'" 
        class="bg-white border-r transition-all duration-300 hidden md:block"
      >
        <el-menu
          :default-active="selectedPortfolioName"
          class="border-none"
          :collapse="isCollapse"
        >
          <div class="px-4 py-3 text-xs font-bold text-gray-400 uppercase tracking-wider">
            我的组合
          </div>
          <el-menu-item 
            v-for="p in portfolios" 
            :key="p.sub_account_name" 
            :index="p.sub_account_name"
            @click="loadPortfolio(p.sub_account_name)"
            :class="{ 'is-active': selectedPortfolioName === p.sub_account_name }"
          >
            <el-icon><FolderChecked /></el-icon>
            <template #title>
              <div class="flex justify-between w-full pr-2">
                <span class="truncate">{{ p.sub_account_name }}</span>
                <span class="text-xs text-gray-400">¥{{ formatNumber(p.asset_value) }}</span>
              </div>
            </template>
          </el-menu-item>
        </el-menu>
      </el-aside>

      <el-main class="bg-gray-50 p-4 md:p-6 overflow-y-auto">
        <!-- 概览卡片 -->
        <el-row :gutter="20" class="mb-6" v-loading="tableLoading">
          <el-col :xs="24" :sm="12" :lg="6" class="mb-4 lg:mb-0">
            <el-card shadow="never" class="border-none">
              <div class="text-xs text-gray-500 mb-1">总资产 (元)</div>
              <div class="text-2xl font-bold text-gray-800">{{ formatNumber(totalAssets) }}</div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6" class="mb-4 lg:mb-0">
            <el-card shadow="never" class="border-none">
              <div class="text-xs text-gray-500 mb-1">持有总收益 (元)</div>
              <div class="text-2xl font-bold" :class="getStatusClass(totalProfit)">
                {{ getPrefix(totalProfit) }}{{ formatNumber(totalProfit) }}
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6" class="mb-4 lg:mb-0">
            <el-card shadow="never" class="border-none">
              <div class="text-xs text-gray-500 mb-1">今日估算收益 (元)</div>
              <div class="text-2xl font-bold" :class="getStatusClass(estProfitValue)">
                {{ getPrefix(estProfitValue) }}{{ formatNumber(estProfitValue) }}
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :lg="6">
            <el-card shadow="never" class="border-none">
              <div class="text-xs text-gray-500 mb-1">整体估值增长率</div>
              <div class="text-2xl font-bold" :class="getStatusClass(estimatedChangeRatio)">
                {{ getPrefix(estimatedChangeRatio) }}{{ formatNumber(estimatedChangeRatio) }}%
              </div>
            </el-card>
          </el-col>
        </el-row>

        <!-- 表格区 -->
        <el-card shadow="never" class="border-none">
          <template #header>
            <div class="flex justify-between items-center">
              <div class="flex items-center gap-3">
                <el-select
                  v-model="selectedPortfolioName"
                  placeholder="选择组合"
                  style="width: 200px"
                  @change="loadPortfolio"
                >
                  <el-option
                    v-for="p in portfolios"
                    :key="p.sub_account_name"
                    :label="p.sub_account_name"
                    :value="p.sub_account_name"
                  >
                    <div class="flex justify-between items-center">
                      <span>{{ p.sub_account_name }}</span>
                      <span class="text-xs text-gray-400">¥{{ formatNumber(p.asset_value) }}</span>
                    </div>
                  </el-option>
                </el-select>
                <el-tag v-if="selectedPortfolioName" type="primary" effect="plain" class="hidden sm:inline-flex">
                  当前选中
                </el-tag>
              </div>
              <div class="flex gap-2">
                <el-button :icon="Refresh" circle @click="loadPortfolio(selectedPortfolioName)" />
                <el-button :icon="Setting" circle />
              </div>
            </div>
          </template>

          <el-table 
            v-loading="tableLoading"
            :data="portfolioDetails" 
            style="width: 100%"
            header-cell-class-name="bg-gray-50 text-xs text-gray-500 font-bold"
          >
            <el-table-column prop="fund_name" label="基金名称" min-width="180" sortable>
              <template #default="{ row }">
                <el-link type="primary" :underline="false" @click="showFundDetail(row.fund_code)" class="font-medium">
                  {{ row.fund_name || '-' }}
                </el-link>
              </template>
            </el-table-column>
            <el-table-column prop="fund_code" label="代码" width="100" sortable />
            <el-table-column prop="asset_value" label="资产市值" align="right" width="140" sortable>
              <template #default="{ row }">
                <span class="font-medium">{{ formatNumber(row.asset_value) }}</span>
              </template>
            </el-table-column>
            <el-table-column prop="hold_profit" label="持有收益" align="right" width="120" sortable>
              <template #default="{ row }">
                <span :class="getStatusClass(row.hold_profit)">
                  {{ getPrefix(row.hold_profit) }}{{ formatNumber(row.hold_profit) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="constant_profit_rate" label="收益率" align="right" width="100" sortable>
              <template #default="{ row }">
                <span :class="getStatusClass(row.constant_profit_rate)">
                  {{ getPrefix(row.constant_profit_rate) }}{{ row.constant_profit_rate.toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column 
              label="今日估算收益" 
              align="right" 
              width="120" 
              sortable 
              :sort-method="(a: AssetDetail, b: AssetDetail) => (a.asset_value * a.estimated_change) - (b.asset_value * b.estimated_change)"
            >
              <template #default="{ row }">
                <span :class="getStatusClass(row.asset_value * row.estimated_change / 100)">
                  {{ getPrefix(row.asset_value * row.estimated_change / 100) }}{{ formatNumber(row.asset_value * row.estimated_change / 100) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="estimated_change" label="今日估值" align="right" width="100" sortable>
              <template #default="{ row }">
                <span :class="getStatusClass(row.estimated_change)">
                  {{ getPrefix(row.estimated_change) }}{{ row.estimated_change.toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column 
              label="预估总收益率" 
              align="right" 
              width="120" 
              sortable 
              :sort-method="(a: AssetDetail, b: AssetDetail) => (a.constant_profit_rate + a.estimated_change) - (b.constant_profit_rate + b.estimated_change)"
            >
              <template #default="{ row }">
                <span :class="getStatusClass(row.constant_profit_rate + row.estimated_change)">
                  {{ getPrefix(row.constant_profit_rate + row.estimated_change) }}{{ (row.constant_profit_rate + row.estimated_change).toFixed(2) }}%
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-main>
    </el-container>

    <!-- 基金详情弹出框 -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="selectedFundDetail?.fund_name || '基金详情'"
      width="600px"
      destroy-on-close
    >
      <div v-loading="detailLoading" class="min-h-[200px]">
        <el-descriptions v-if="selectedFundDetail" :column="1" border>
          <el-descriptions-item 
            v-for="key in fundFieldOrder" 
            :key="key" 
            :label="fundFieldMap[key]"
            v-show="selectedFundDetail[key] !== undefined"
          >
            <template v-if="typeof selectedFundDetail[key] === 'number'">
              <span :class="{
                'text-red-500': key.includes('change') && selectedFundDetail[key] > 0,
                'text-green-500': key.includes('change') && selectedFundDetail[key] < 0
              }">
                {{ formatNumber(selectedFundDetail[key]) }}{{ key.includes('change') || key.includes('return') ? '%' : '' }}
              </span>
            </template>
            <template v-else-if="typeof selectedFundDetail[key] === 'boolean'">
              <el-tag :type="selectedFundDetail[key] ? 'success' : 'danger'">{{ selectedFundDetail[key] ? '是' : '否' }}</el-tag>
            </template>
            <template v-else>
              {{ selectedFundDetail[key] }}
            </template>
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else-if="!detailLoading" description="暂无数据" />
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="detailDialogVisible = false">关闭</el-button>
        </span>
      </template>
    </el-dialog>
  </el-container>
</template>

<style scoped>
.bg-brand {
  background-color: #722ed1;
}
</style>
