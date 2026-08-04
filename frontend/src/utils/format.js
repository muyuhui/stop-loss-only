export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '--'
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '--'
}

// API monetary fields may be Decimal strings. Formatting intentionally does not
// perform portfolio arithmetic; it only renders a bounded display value.
export function formatDecimal(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '--'
  const raw = String(value).trim()
  if (!/^[+-]?\d+(\.\d+)?$/.test(raw)) return '--'
  const [integer, fraction = ''] = raw.replace(/^\+/, '').split('.')
  const sign = integer.startsWith('-') ? '-' : ''
  const whole = integer.replace('-', '').replace(/\B(?=(\d{3})+(?!\d))/g, ',')
  return `${sign}${whole}${digits > 0 ? `.${fraction.padEnd(digits, '0').slice(0, digits)}` : ''}`
}

export function formatMoney(value, digits = 2) {
  const formatted = formatDecimal(value, digits)
  return formatted === '--' ? '--' : `¥${formatted}`
}

export function formatAssetMoney(value, assetType) {
  return formatMoney(value, assetType === 'fund' ? 3 : 2)
}

export function formatSignedPercent(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '--'
  const number = Number(value)
  if (!Number.isFinite(number)) return '--'
  const sign = number > 0 ? '+' : ''
  return `${sign}${number.toFixed(digits)}%`
}

export function valueTone(value) {
  if (value === null || value === undefined || value === '') return 'muted'
  const number = Number(value)
  if (!Number.isFinite(number) || number === 0) return 'muted'
  return number > 0 ? 'profit' : 'loss'
}

/**
 * 平仓确认前的展示性毛盈亏估算：(平仓价 - 买入价) × 数量。
 * 仅用于确认参考，权威盈亏以后端记录为准；输入无效返回 null。
 */
export function estimateRealizedProfitLoss(closePrice, buyPrice, quantity) {
  if (
    closePrice === null || closePrice === undefined || closePrice === ''
    || buyPrice === null || buyPrice === undefined || buyPrice === ''
    || quantity === null || quantity === undefined || quantity === ''
  ) return null
  const close = Number(closePrice)
  const cost = Number(buyPrice)
  const shares = Number(quantity)
  if (![close, cost, shares].every(Number.isFinite) || close <= 0 || shares <= 0) return null
  return (close - cost) * shares
}

export function stopLossRisk(distance, status = 'holding') {
  if (status === 'triggered') return { level: 'danger', label: '已触发止损' }
  if (distance === null || distance === undefined || distance === '') return { level: 'muted', label: '风险未知' }
  const number = Number(distance)
  if (!Number.isFinite(number)) return { level: 'muted', label: '风险未知' }
  if (number < 3) return { level: 'danger', label: '非常接近止损' }
  if (number < 8) return { level: 'warning', label: '接近止损' }
  return { level: 'safe', label: '距离安全' }
}

export function formatTime(value) {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}
