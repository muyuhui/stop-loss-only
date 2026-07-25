import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

export const PRICE_REFRESH_TIMEOUT_MS = 60000

const REFRESH_ERROR_MESSAGES = {
  refresh_busy: '已有刷新正在运行，请稍后再试。',
  database_busy: '数据库正忙，请稍后重试。',
  refresh_failed: '价格刷新失败，请按关联编号检查服务日志。',
}

export function refreshErrorMessage(error) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) return '刷新参数无效，请检查输入。'
  return REFRESH_ERROR_MESSAGES[detail?.error_code] || '价格刷新失败，请稍后重试。'
}

export function requestPriceRefresh(params = undefined) {
  return api.post('/prices/refresh', undefined, { params, timeout: PRICE_REFRESH_TIMEOUT_MS })
}

export function requestHoldingHistory(holdingId, range = '3m') {
  return api.get(`/holdings/${holdingId}/history`, { params: { range }, timeout: 60000 })
}

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    let message = '请求失败'
    if (Array.isArray(detail)) {
      message = detail.map(d => d.msg).join('；')
    } else if (typeof detail === 'string') {
      message = detail
    } else if (detail?.error_code && REFRESH_ERROR_MESSAGES[detail.error_code]) {
      message = REFRESH_ERROR_MESSAGES[detail.error_code]
    } else if (detail?.message) {
      message = detail.message
    }
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default api
