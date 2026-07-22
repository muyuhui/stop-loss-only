export function formatNumber(value, digits = 2) {
  const number = Number(value)
  return Number.isFinite(number) ? number.toFixed(digits) : '--'
}

export function formatMoney(value, digits = 2) {
  const formatted = formatNumber(value, digits)
  return formatted === '--' ? '--' : `¥${formatted}`
}

export function formatAssetMoney(value, assetType) {
  return formatMoney(value, assetType === 'fund' ? 3 : 2)
}

export function formatSignedPercent(value, digits = 2) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '--'
  const sign = number > 0 ? '+' : ''
  return `${sign}${number.toFixed(digits)}%`
}

export function valueTone(value) {
  const number = Number(value)
  if (!Number.isFinite(number) || number === 0) return 'muted'
  return number > 0 ? 'profit' : 'loss'
}

export function stopLossRisk(distance, status = 'holding') {
  if (status === 'triggered') return { level: 'danger', label: '已触发止损' }
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
