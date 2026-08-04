const SESSION_LABELS = {
  pre_market: '盘前',
  open: '交易中',
  lunch: '午休',
  closed: '已收盘',
}

/**
 * 交易时段徽标文本；未知或缺失返回 null（调用方降级不显示）。
 * 与后端 market_clock 的时间语义一致，不判定节假日。
 */
export function formatMarketSession(session) {
  return SESSION_LABELS[session] || null
}

/**
 * 行情时效文本：<60s 为"刚刚"，<60min 为"N 分钟前"，更早显示本地时间。
 * 无 quotedAt 或解析失败返回 null。
 */
export function formatQuoteFreshness(quotedAt, now = Date.now()) {
  if (!quotedAt) return null
  const time = new Date(quotedAt).getTime()
  if (Number.isNaN(time)) return null
  const ageMinutes = Math.floor((now - time) / 60000)
  if (ageMinutes <= 0) return '刚刚'
  if (ageMinutes < 60) return `${ageMinutes} 分钟前`
  return new Date(quotedAt).toLocaleString('zh-CN', { hour12: false })
}

/**
 * 持仓卡片时效行：有行情显示"行情 X"，否则显示明确的"未定价/行情不可用"。
 */
export function quoteFreshnessText(quotedAt) {
  const text = formatQuoteFreshness(quotedAt)
  return text ? `行情 ${text}` : '未定价/行情不可用'
}
