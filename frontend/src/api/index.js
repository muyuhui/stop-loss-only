import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    let message = '请求失败'
    if (Array.isArray(detail)) {
      message = detail.map(d => d.msg).join('；')
    } else if (typeof detail === 'string') {
      message = detail
    } else if (detail) {
      message = JSON.stringify(detail)
    }
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default api
