<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  ArrowDown,
  ArrowUp,
  CaretRight,
  Delete,
  Edit,
  Plus,
  Refresh,
  TrendCharts,
  UserFilled
} from '@element-plus/icons-vue'
import { getMockFundDetail, getMockPortfolioResponse, mockPortfoliosResponse } from './mock/data'

axios.defaults.baseURL = import.meta.env.VITE_API_BASE_URL || ''
const useMockPortfolio = import.meta.env.VITE_USE_MOCK === 'true'

interface AssetDetail {
  fund_name: string
  fund_code: string
  asset_value: number
  hold_profit: number
  hold_profit_rate: number
  constant_profit: number
  constant_profit_rate: number
  estimated_change: number
  profit_value: number
  [key: string]: any
}

interface Portfolio {
  sub_account_name: string
  asset_value: number
}

interface ScheduledTask {
  task_id: number
  task_name: string
  cron_expression: string
  policy: string
  handler: string
  payload: string | null
  payload_object?: Record<string, any> | any[]
  description: string | null
  is_enabled: boolean
  is_deleted: boolean
  last_executed_at: string | null
  last_executed_status: string | null
  last_error_message: string | null
  next_run_at: string | null
  cron_error: string | null
  created_at: string | null
  updated_at: string | null
}

const activeView = ref<'portfolio' | 'scheduled-tasks'>('portfolio')

const portfolios = ref<Portfolio[]>([])
const selectedPortfolioName = ref('')
const portfolioDetails = ref<AssetDetail[]>([])
const sortField = ref<string>('constant_profit_rate')
const sortOrder = ref<'asc' | 'desc'>('desc')
const sortedPortfolioDetails = computed(() => {
  const data = [...portfolioDetails.value]
  const field = sortField.value as keyof AssetDetail
  const order = sortOrder.value === 'asc' ? 1 : -1
  data.sort((a, b) => {
    const va = a[field] ?? 0
    const vb = b[field] ?? 0
    if (typeof va === 'string' && typeof vb === 'string') {
      return order * va.localeCompare(vb, 'zh-CN')
    }
    return order * (Number(va) - Number(vb))
  })
  return data
})
const sortOptions = [
  { label: '资产市值', value: 'asset_value' },
  { label: '持有收益', value: 'hold_profit' },
  { label: '收益率', value: 'constant_profit_rate' },
  { label: '今日估值', value: 'estimated_change' },
  { label: '基金名称', value: 'fund_name' }
]
const totalAssets = ref(0)
const totalProfit = ref(0)
const totalProfitValue = ref(0)
const estimatedChangeRatio = ref(0)
const constantProfit = ref(0)
const profitValue = ref(0)
const portfolioLoading = ref(false)
const detailDialogVisible = ref(false)
const selectedFundDetail = ref<Record<string, any> | null>(null)
const detailLoading = ref(false)

const tasks = ref<ScheduledTask[]>([])
const taskLoading = ref(false)
const schedulerState = ref<Record<string, any>>({})
const executingTaskIds = ref<number[]>([])
const executionDialogVisible = ref(false)
const latestExecutionResult = ref<Record<string, any> | null>(null)
const taskDialogVisible = ref(false)
const taskDialogTitle = ref('新增定时任务')
const taskSubmitting = ref(false)
const editingTaskId = ref<number | null>(null)
const taskFormRef = ref<FormInstance>()
const taskForm = reactive({
  task_name: '',
  cron_expression: '',
  policy: '',
  handler: '',
  payload: '{}',
  description: '',
  is_enabled: true
})

const fundFieldMap: Record<string, string> = {
  fund_name: '基金名称',
  fund_code: '基金代码',
  fund_type: '基金类型',
  fund_sub_type: '基金子类型',
  index_code: '指数代码',
  nav: '当前净值',
  acc_nav: '累计净值',
  nav_date: '净值日期',
  nav_change: '净值涨跌幅',
  estimated_value: '估算净值',
  estimated_change: '估算涨跌幅',
  estimated_time: '估算时间',
  nav_5day_avg: '5日均值',
  week_return: '周收益率',
  month_return: '近一月收益率',
  three_month_return: '3个月收益率',
  six_month_return: '6个月收益率',
  this_year_return: '今年以来收益率',
  volatility: '波动率',
  rank_30day: '30日排名',
  rank_100day: '百日排名',
  can_purchase: '可买入',
  can_redeem: '可赎回',
  max_purchase: '单日限额'
}

const fundFieldOrder = [
  'fund_name',
  'fund_code',
  'fund_type',
  'fund_sub_type',
  'index_code',
  'nav',
  'acc_nav',
  'nav_date',
  'nav_change',
  'estimated_value',
  'estimated_change',
  'estimated_time',
  'nav_5day_avg',
  'week_return',
  'month_return',
  'three_month_return',
  'six_month_return',
  'this_year_return',
  'volatility',
  'rank_30day',
  'rank_100day',
  'can_purchase',
  'can_redeem',
  'max_purchase'
]

const estProfitValue = computed(() => (estimatedChangeRatio.value * totalAssets.value) / 100)
const currentViewLabel = computed(() =>
  activeView.value === 'portfolio' ? '组合看板' : '定时任务管理'
)

const cronFieldTokenPattern = /^[A-Za-z0-9_*?,/\-L]+$/

const validateCronExpression = (value: string) => {
  const expr = value.trim()
  if (!expr) {
    return '请输入 Cron 表达式'
  }

  let normalizedExpr = expr
  if (normalizedExpr.startsWith('CRON_TZ=')) {
    const parts = normalizedExpr.split(/\s+/, 2)
    if (parts.length < 2 || !parts[0].includes('=')) {
      return 'CRON_TZ 格式不正确'
    }
    normalizedExpr = normalizedExpr.slice(parts[0].length).trim()
  }

  if (normalizedExpr.startsWith('@every')) {
    if (!/^@every\s+\d+(?:\.\d+)?(ns|us|µs|ms|s|m|h)$/i.test(normalizedExpr)) {
      return 'Cron 表达式格式不正确'
    }
    return ''
  }

  const fields = normalizedExpr.split(/\s+/).filter(Boolean)
  if (![5, 6, 7].includes(fields.length)) {
    return 'Cron 表达式必须为 5、6 或 7 段'
  }
  if (!fields.every((field) => cronFieldTokenPattern.test(field))) {
    return 'Cron 表达式包含非法字符'
  }
  return ''
}

const taskFormRules: FormRules = {
  task_name: [{ required: true, message: '请输入任务名', trigger: ['blur', 'change'] }],
  policy: [{ required: true, message: '请输入函数名', trigger: ['blur', 'change'] }],
  handler: [{ required: true, message: '请输入处理器', trigger: ['blur', 'change'] }],
  cron_expression: [
    {
      validator: (_rule, value, callback) => {
        const errorMessage = validateCronExpression(String(value ?? ''))
        callback(errorMessage ? new Error(errorMessage) : undefined)
      },
      trigger: ['blur', 'change']
    }
  ],
  payload: [
    {
      validator: (_rule, value, callback) => {
        const payloadText = String(value ?? '').trim()
        if (!payloadText) {
          callback(new Error('请输入 Payload JSON'))
          return
        }
        try {
          JSON.parse(payloadText)
          callback()
        } catch (_error) {
          callback(new Error('Payload JSON 格式不正确'))
        }
      },
      trigger: ['blur', 'change']
    }
  ]
}

const formatNumber = (num: number) =>
  Number(num || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })

const formatDateTime = (value: string | null) => {
  if (!value) return '-'
  return value.replace('T', ' ').replace(/\.\d+/, '')
}

const getStatusClass = (num: number) => {
  if (num > 0) return 'text-[#f5222d]'
  if (num < 0) return 'text-[#52c41a]'
  return 'text-gray-700'
}

const getPrefix = (num: number) => (num > 0 ? '+' : '')

const showFundDetail = async (fundCode: string) => {
  detailDialogVisible.value = true
  detailLoading.value = true
  try {
    if (useMockPortfolio) {
      selectedFundDetail.value = getMockFundDetail(fundCode)
      return
    }
    const res = await axios.get(`/api/fund/${fundCode}`)
    selectedFundDetail.value = res.data
  } catch (error) {
    console.error('Fetch fund detail error:', error)
    ElMessage.error('获取基金详情失败')
  } finally {
    detailLoading.value = false
  }
}

const fetchPortfolios = async () => {
  try {
    if (useMockPortfolio) {
      portfolios.value = mockPortfoliosResponse.portfolios
      if (mockPortfoliosResponse.selected_portfolio_name && !selectedPortfolioName.value) {
        await loadPortfolio(mockPortfoliosResponse.selected_portfolio_name)
      } else if (!selectedPortfolioName.value && portfolios.value.length > 0) {
        await loadPortfolio(portfolios.value[0].sub_account_name)
      }
      return
    }
    const res = await axios.get('/api/portfolios')
    portfolios.value = res.data.portfolios || []
    if (res.data.selected_portfolio_name && !selectedPortfolioName.value) {
      await loadPortfolio(res.data.selected_portfolio_name)
    } else if (!selectedPortfolioName.value && portfolios.value.length > 0) {
      await loadPortfolio(portfolios.value[0].sub_account_name)
    }
  } catch (error) {
    console.error('Fetch portfolios error:', error)
    ElMessage.error('获取组合列表失败')
  }
}

const loadPortfolio = async (name: string) => {
  if (!name) return
  selectedPortfolioName.value = name
  portfolioLoading.value = true
  totalAssets.value = 0
  totalProfit.value = 0
  totalProfitValue.value = 0
  estimatedChangeRatio.value = 0
  constantProfit.value = 0
  profitValue.value = 0
  portfolioDetails.value = []

  try {
    const data = useMockPortfolio
      ? getMockPortfolioResponse(name)
      : (await axios.get(`/api/portfolio/${encodeURIComponent(name)}`)).data

    const rawDetails = Array.isArray(data?.portfolio_details) ? data.portfolio_details : []
    const adaptedDetails = rawDetails.map((detail: any) => ({
      ...detail,
      hold_profit: typeof detail?.constant_profit === 'number' ? detail.constant_profit : detail.hold_profit,
      hold_profit_rate:
        typeof detail?.constant_profit_rate === 'number' ? detail.constant_profit_rate : detail.hold_profit_rate
    }))

    portfolioDetails.value = adaptedDetails
    totalAssets.value = data.total_assets || 0
    totalProfit.value = adaptedDetails.reduce(
      (acc: number, current: any) => acc + (typeof current?.hold_profit === 'number' ? current.hold_profit : 0),
      0
    )
    totalProfitValue.value = data.total_profit_value || 0
    estimatedChangeRatio.value = data.estimated_portfolio_change_ratio || 0
    constantProfit.value = data.constant_profit || 0
    profitValue.value = data.profit_value || 0
  } catch (error) {
    console.error('Load portfolio error:', error)
    ElMessage.error('加载组合详情失败')
  } finally {
    portfolioLoading.value = false
  }
}

const refreshPortfolio = async () => {
  if (!selectedPortfolioName.value) return
  if (!useMockPortfolio) {
    await axios.post('/api/cache/clear')
  }
  await loadPortfolio(selectedPortfolioName.value)
}

const fetchTasks = async () => {
  taskLoading.value = true
  try {
    const res = await axios.get('/api/scheduled-tasks')
    tasks.value = res.data.tasks || []
    schedulerState.value = res.data.scheduler || {}
  } catch (error) {
    console.error('Fetch tasks error:', error)
    ElMessage.error('获取定时任务失败')
  } finally {
    taskLoading.value = false
  }
}

const reloadTasks = async (showMessage = false) => {
  try {
    const res = await axios.post('/api/scheduled-tasks/reload')
    schedulerState.value = res.data.result || {}
    await fetchTasks()
    if (showMessage) {
      ElMessage.success('定时任务已刷新并生效')
    }
  } catch (error) {
    console.error('Reload tasks error:', error)
    ElMessage.error('刷新定时任务失败')
  }
}

const switchView = async (view: 'portfolio' | 'scheduled-tasks') => {
  activeView.value = view
  if (view === 'portfolio') {
    if (!selectedPortfolioName.value && portfolios.value.length > 0) {
      await loadPortfolio(portfolios.value[0].sub_account_name)
    }
    return
  }
  await fetchTasks()
}

const resetTaskForm = () => {
  editingTaskId.value = null
  taskDialogTitle.value = '新增定时任务'
  taskForm.task_name = ''
  taskForm.cron_expression = ''
  taskForm.policy = ''
  taskForm.handler = ''
  taskForm.payload = '{}'
  taskForm.description = ''
  taskForm.is_enabled = true
  nextTick(() => taskFormRef.value?.clearValidate())
}

const openCreateTaskDialog = () => {
  resetTaskForm()
  taskDialogVisible.value = true
  nextTick(() => taskFormRef.value?.clearValidate())
}

const openEditTaskDialog = (task: ScheduledTask) => {
  editingTaskId.value = task.task_id
  taskDialogTitle.value = `编辑任务 - ${task.task_name}`
  taskForm.task_name = task.task_name
  taskForm.cron_expression = task.cron_expression
  taskForm.policy = task.policy
  taskForm.handler = task.handler
  taskForm.payload = task.payload
    ? JSON.stringify(task.payload_object ?? JSON.parse(task.payload), null, 2)
    : '{}'
  taskForm.description = task.description || ''
  taskForm.is_enabled = task.is_enabled
  taskDialogVisible.value = true
  nextTick(() => taskFormRef.value?.clearValidate())
}

const buildTaskRequestPayload = () => {
  let parsedPayload: Record<string, any> | any[] | string = {}
  const payloadText = taskForm.payload.trim()
  if (payloadText) {
    parsedPayload = JSON.parse(payloadText)
  }
  return {
    task_name: taskForm.task_name.trim(),
    cron_expression: taskForm.cron_expression.trim(),
    policy: taskForm.policy.trim(),
    handler: taskForm.handler.trim(),
    payload: parsedPayload,
    description: taskForm.description.trim(),
    is_enabled: taskForm.is_enabled
  }
}

const submitTask = async () => {
  try {
    const isValid = await taskFormRef.value?.validate().catch(() => false)
    if (!isValid) {
      ElMessage.error('请先修正表单校验错误')
      return
    }
    taskSubmitting.value = true
    const payload = buildTaskRequestPayload()
    if (editingTaskId.value) {
      await axios.put(`/api/scheduled-tasks/${editingTaskId.value}`, payload)
    } else {
      await axios.post('/api/scheduled-tasks', payload)
    }
    taskDialogVisible.value = false
    await reloadTasks()
    ElMessage.success(editingTaskId.value ? '任务已更新并生效' : '任务已创建并生效')
  } catch (error) {
    console.error('Submit task error:', error)
    ElMessage.error('保存任务失败，请检查 cron 或 payload JSON 格式')
  } finally {
    taskSubmitting.value = false
  }
}

const updateTaskEnabled = async (task: ScheduledTask) => {
  try {
    await axios.put(`/api/scheduled-tasks/${task.task_id}`, {
      is_enabled: task.is_enabled
    })
    await reloadTasks()
    ElMessage.success('启用状态已更新并生效')
  } catch (error) {
    console.error('Update task enabled error:', error)
    task.is_enabled = !task.is_enabled
    ElMessage.error('更新启用状态失败')
  }
}

const deleteTask = async (task: ScheduledTask) => {
  await ElMessageBox.confirm(`确认逻辑删除任务「${task.task_name}」吗？`, '删除任务', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消'
  })
  try {
    await axios.delete(`/api/scheduled-tasks/${task.task_id}`)
    await reloadTasks()
    ElMessage.success('任务已删除并生效')
  } catch (error) {
    console.error('Delete task error:', error)
    ElMessage.error('删除任务失败')
  }
}

const runTaskNow = async (task: ScheduledTask) => {
  if (executingTaskIds.value.includes(task.task_id)) {
    return
  }
  try {
    executingTaskIds.value = [...executingTaskIds.value, task.task_id]
    const res = await axios.post(`/api/scheduled-tasks/${task.task_id}/run`)
    const execution = res.data?.result?.execution
    latestExecutionResult.value = execution || null
    executionDialogVisible.value = true
    await fetchTasks()
    if (execution?.success) {
      ElMessage.success(`任务「${task.task_name}」已立即执行`)
    } else {
      ElMessage.error(`任务执行失败：${execution?.error_message || '未知错误'}`)
    }
  } catch (error) {
    console.error('Run task now error:', error)
    ElMessage.error('立即执行失败')
  } finally {
    executingTaskIds.value = executingTaskIds.value.filter((id) => id !== task.task_id)
  }
}

onMounted(async () => {
  await Promise.all([fetchPortfolios(), fetchTasks()])
})
</script>

<template>
  <el-container class="min-h-screen">
    <el-header class="bg-brand text-white flex items-center justify-between px-4 md:px-6 h-14 shadow-md gap-3">
      <el-dropdown trigger="click" @command="switchView">
        <div class="font-bold text-base md:text-lg flex items-center gap-2 cursor-pointer outline-none">
          <el-icon><TrendCharts /></el-icon>
          <span>基金系统控制台</span>
          <el-tag size="small" effect="dark">{{ currentViewLabel }}</el-tag>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="portfolio">组合看板</el-dropdown-item>
            <el-dropdown-item command="scheduled-tasks">定时任务管理</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <div class="flex items-center gap-2 md:gap-3">
        <el-tag type="info" effect="dark" class="hidden sm:inline-flex">
          {{ useMockPortfolio ? '组合看板使用 Mock' : '生产环境' }}
        </el-tag>
        <div class="flex items-center gap-2 min-w-0">
          <el-avatar :size="28"><UserFilled /></el-avatar>
          <span class="hidden sm:inline">管理员</span>
        </div>
      </div>
    </el-header>

    <el-main class="bg-gray-50 p-3 md:p-6">
      <div v-if="activeView === 'scheduled-tasks'">
          <el-card shadow="never" class="border-none">
            <template #header>
              <div class="flex flex-wrap gap-3 items-center justify-between">
                <div class="text-lg font-semibold">定时任务管理</div>
                <div class="flex flex-wrap gap-2">
                  <el-button type="primary" :icon="Plus" @click="openCreateTaskDialog">新增任务</el-button>
                </div>
              </div>
            </template>

            <div class="mb-4">
              <span class="text-sm text-gray-500 mr-2">当前任务数</span>
              <span class="text-lg font-bold">{{ tasks.length }}</span>
            </div>

            <div class="hidden lg:block overflow-x-auto">
              <el-table
                v-loading="taskLoading"
                :data="tasks"
                style="width: 100%"
                header-cell-class-name="bg-gray-50 text-xs text-gray-500 font-bold"
              >
                <el-table-column prop="task_id" label="ID" width="80" />
                <el-table-column prop="task_name" label="任务名" min-width="220" />
                <el-table-column prop="policy" label="函数名" min-width="170" />
                <el-table-column prop="handler" label="处理器" min-width="180" />
                <el-table-column prop="cron_expression" label="Cron" min-width="240" show-overflow-tooltip />
                <el-table-column label="启用" width="90" align="center">
                  <template #default="{ row }">
                    <el-switch v-model="row.is_enabled" @change="updateTaskEnabled(row)" />
                  </template>
                </el-table-column>
                <el-table-column label="下次执行" min-width="180">
                  <template #default="{ row }">
                    <div>{{ formatDateTime(row.next_run_at) }}</div>
                    <div v-if="row.cron_error" class="text-xs text-red-500">{{ row.cron_error }}</div>
                  </template>
                </el-table-column>
                <el-table-column label="最后执行" min-width="200">
                  <template #default="{ row }">
                    <div>{{ formatDateTime(row.last_executed_at) }}</div>
                    <el-tag
                      v-if="row.last_executed_status"
                      size="small"
                      :type="row.last_executed_status === 'SUCCESS' ? 'success' : 'danger'"
                    >
                      {{ row.last_executed_status }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column label="错误信息" min-width="220" show-overflow-tooltip>
                  <template #default="{ row }">
                    {{ row.last_error_message || '-' }}
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="220" fixed="right">
                  <template #default="{ row }">
                    <div class="flex gap-2 flex-wrap">
                      <el-button
                        type="success"
                        link
                        :icon="CaretRight"
                        :loading="executingTaskIds.includes(row.task_id)"
                        @click="runTaskNow(row)"
                      >
                        立即执行
                      </el-button>
                      <el-button type="primary" link :icon="Edit" @click="openEditTaskDialog(row)">编辑</el-button>
                      <el-button type="danger" link :icon="Delete" @click="deleteTask(row)">删除</el-button>
                    </div>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div class="grid grid-cols-1 gap-3 lg:hidden" v-loading="taskLoading">
              <el-card v-for="task in tasks" :key="task.task_id" shadow="hover">
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="font-semibold break-all">{{ task.task_name }}</div>
                    <div class="text-sm text-gray-500 break-all">{{ task.policy }}</div>
                  </div>
                  <el-switch v-model="task.is_enabled" @change="updateTaskEnabled(task)" />
                </div>
                <div class="mt-3 text-sm text-gray-600 space-y-2">
                  <div><span class="text-gray-400">处理器</span> {{ task.handler }}</div>
                  <div class="break-all"><span class="text-gray-400">Cron</span> {{ task.cron_expression }}</div>
                  <div><span class="text-gray-400">下次执行</span> {{ formatDateTime(task.next_run_at) }}</div>
                  <div class="flex items-center gap-2 flex-wrap">
                    <span class="text-gray-400">最后执行</span>
                    <span>{{ formatDateTime(task.last_executed_at) }}</span>
                    <el-tag
                      v-if="task.last_executed_status"
                      size="small"
                      :type="task.last_executed_status === 'SUCCESS' ? 'success' : 'danger'"
                    >
                      {{ task.last_executed_status }}
                    </el-tag>
                  </div>
                  <div v-if="task.cron_error" class="text-red-500 break-all">{{ task.cron_error }}</div>
                  <div v-if="task.last_error_message" class="text-red-500 break-all">{{ task.last_error_message }}</div>
                </div>
                <div class="mt-4 flex flex-wrap gap-2">
                  <el-button
                    type="success"
                    plain
                    size="small"
                    :icon="CaretRight"
                    :loading="executingTaskIds.includes(task.task_id)"
                    @click="runTaskNow(task)"
                  >
                    立即执行
                  </el-button>
                  <el-button type="primary" plain size="small" :icon="Edit" @click="openEditTaskDialog(task)">
                    编辑
                  </el-button>
                  <el-button type="danger" plain size="small" :icon="Delete" @click="deleteTask(task)">
                    删除
                  </el-button>
                </div>
              </el-card>
            </div>
          </el-card>
      </div>

      <div v-else>
          <el-row :gutter="20" class="mb-6" v-loading="portfolioLoading">
            <el-col :xs="24" :sm="12" :lg="6" class="mb-4 lg:mb-0">
              <el-card shadow="never" class="border-none">
                <div class="text-xs text-gray-500 mb-1">{{ selectedPortfolioName || '当前组合' }} · 总资产 (元)</div>
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

          <el-card shadow="never" class="border-none">
            <template #header>
              <div class="flex flex-wrap gap-3 items-center justify-between">
                <div class="flex flex-col gap-2 min-w-0">
                  <div class="text-sm font-medium text-gray-700 break-all">
                    当前组合：{{ selectedPortfolioName || '-' }}
                  </div>
                  <div class="flex items-center gap-3 flex-wrap">
                    <el-select
                      v-model="selectedPortfolioName"
                      placeholder="选择组合"
                      class="!w-full sm:!w-[260px]"
                      @change="loadPortfolio"
                    >
                      <el-option
                        v-for="portfolio in portfolios"
                        :key="portfolio.sub_account_name"
                        :label="portfolio.sub_account_name"
                        :value="portfolio.sub_account_name"
                      />
                    </el-select>
                  </div>
                </div>
                <div class="flex items-center gap-2 flex-wrap">
                  <el-select
                    v-model="sortField"
                    class="!w-[130px]"
                    size="small"
                    placeholder="排序字段"
                  >
                    <el-option
                      v-for="opt in sortOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                  <el-button
                    size="small"
                    :icon="sortOrder === 'asc' ? ArrowUp : ArrowDown"
                    @click="sortOrder = sortOrder === 'asc' ? 'desc' : 'asc'"
                  >
                    {{ sortOrder === 'asc' ? '升序' : '降序' }}
                  </el-button>
                  <el-button :icon="Refresh" @click="refreshPortfolio">刷新组合</el-button>
                </div>
              </div>
            </template>

            <div class="hidden md:block overflow-x-auto">
              <el-table
                v-loading="portfolioLoading"
                :data="sortedPortfolioDetails"
                style="width: 100%"
                header-cell-class-name="bg-gray-50 text-xs text-gray-500 font-bold"
              >
                <el-table-column prop="fund_name" label="基金名称" min-width="180" sortable>
                  <template #default="{ row }">
                    <el-link type="primary" :underline="false" @click="showFundDetail(row.fund_code)">
                      {{ row.fund_name || '-' }}
                    </el-link>
                  </template>
                </el-table-column>
                <el-table-column prop="fund_code" label="代码" width="100" sortable />
                <el-table-column prop="asset_value" label="资产市值" align="right" width="140" sortable>
                  <template #default="{ row }">
                    {{ formatNumber(row.asset_value) }}
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
                      {{ getPrefix(row.constant_profit_rate) }}{{ Number(row.constant_profit_rate || 0).toFixed(2) }}%
                    </span>
                  </template>
                </el-table-column>
                <el-table-column prop="estimated_change" label="今日估值" align="right" width="110" sortable>
                  <template #default="{ row }">
                    <span :class="getStatusClass(row.estimated_change)">
                      {{ getPrefix(row.estimated_change) }}{{ Number(row.estimated_change || 0).toFixed(2) }}%
                    </span>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <div class="grid grid-cols-1 gap-3 md:hidden" v-loading="portfolioLoading">
              <el-card v-for="row in sortedPortfolioDetails" :key="row.fund_code" shadow="hover">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <el-link type="primary" :underline="false" @click="showFundDetail(row.fund_code)">
                      {{ row.fund_name || '-' }}
                    </el-link>
                    <div class="text-sm text-gray-500">{{ row.fund_code }}</div>
                  </div>
                  <div class="text-right">
                    <div class="font-semibold">{{ formatNumber(row.asset_value) }}</div>
                    <div class="text-xs text-gray-400">资产市值</div>
                  </div>
                </div>
                <div class="grid grid-cols-2 gap-3 mt-4 text-sm">
                  <div>
                    <div class="text-gray-400">持有收益</div>
                    <div :class="getStatusClass(row.hold_profit)">
                      {{ getPrefix(row.hold_profit) }}{{ formatNumber(row.hold_profit) }}
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-400">收益率</div>
                    <div :class="getStatusClass(row.constant_profit_rate)">
                      {{ getPrefix(row.constant_profit_rate) }}{{ Number(row.constant_profit_rate || 0).toFixed(2) }}%
                    </div>
                  </div>
                  <div>
                    <div class="text-gray-400">今日估值</div>
                    <div :class="getStatusClass(row.estimated_change)">
                      {{ getPrefix(row.estimated_change) }}{{ Number(row.estimated_change || 0).toFixed(2) }}%
                    </div>
                  </div>
                </div>
              </el-card>
            </div>
          </el-card>
      </div>
    </el-main>

    <el-dialog v-model="taskDialogVisible" :title="taskDialogTitle" width="min(720px, 92vw)" destroy-on-close>
      <el-form ref="taskFormRef" :model="taskForm" :rules="taskFormRules" label-width="120px" status-icon>
        <el-form-item label="任务名" prop="task_name">
          <el-input v-model="taskForm.task_name" placeholder="例如 redeem_gold_portfolio_13918199137" />
        </el-form-item>
        <el-form-item label="函数名" prop="policy">
          <el-input v-model="taskForm.policy" placeholder="例如 redeem_gold_portfolio" />
        </el-form-item>
        <el-form-item label="处理器" prop="handler">
          <el-input v-model="taskForm.handler" placeholder="例如 index.redeem_gold_portfolio" />
        </el-form-item>
        <el-form-item label="Cron 表达式" prop="cron_expression">
          <el-input v-model="taskForm.cron_expression" placeholder="例如 CRON_TZ=Asia/Shanghai 0 55 14 * * 1-5" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="taskForm.is_enabled" />
        </el-form-item>
        <el-form-item label="Payload JSON" prop="payload">
          <el-input
            v-model="taskForm.payload"
            type="textarea"
            :rows="8"
            placeholder='{"account":"13918199137","password":"***"}'
          />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="taskDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="taskSubmitting" @click="submitTask">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="detailDialogVisible"
      :title="selectedFundDetail?.fund_name || '基金详情'"
      width="min(600px, 92vw)"
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
              <span
                :class="{
                  'text-red-500': key.includes('change') && selectedFundDetail[key] > 0,
                  'text-green-500': key.includes('change') && selectedFundDetail[key] < 0
                }"
              >
                {{ formatNumber(selectedFundDetail[key]) }}
                {{ key.includes('change') || key.includes('return') || key === 'volatility' ? '%' : '' }}
              </span>
            </template>
            <template v-else-if="typeof selectedFundDetail[key] === 'boolean'">
              <el-tag :type="selectedFundDetail[key] ? 'success' : 'danger'">
                {{ selectedFundDetail[key] ? '是' : '否' }}
              </el-tag>
            </template>
            <template v-else>
              {{ selectedFundDetail[key] }}
            </template>
          </el-descriptions-item>
        </el-descriptions>
        <el-empty v-else-if="!detailLoading" description="暂无数据" />
      </div>
      <template #footer>
        <el-button @click="detailDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="executionDialogVisible" title="任务执行结果" width="min(720px, 92vw)" destroy-on-close>
      <el-descriptions v-if="latestExecutionResult" :column="1" border>
        <el-descriptions-item label="执行状态">
          <el-tag :type="latestExecutionResult.success ? 'success' : 'danger'">
            {{ latestExecutionResult.status || '-' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="触发来源">
          {{ latestExecutionResult.trigger_source || '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="开始时间">
          {{ formatDateTime(latestExecutionResult.started_at || null) }}
        </el-descriptions-item>
        <el-descriptions-item label="结束时间">
          {{ formatDateTime(latestExecutionResult.finished_at || null) }}
        </el-descriptions-item>
        <el-descriptions-item label="耗时(秒)">
          {{ latestExecutionResult.duration_seconds ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="错误摘要">
          <pre class="whitespace-pre-wrap break-words text-sm m-0">{{ latestExecutionResult.error_message || '-' }}</pre>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button type="primary" @click="executionDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </el-container>
</template>

<style scoped>
.bg-brand {
  background-color: #722ed1;
}
</style>
