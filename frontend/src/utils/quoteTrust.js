const STATE_META = {
  unpriced: { label: '未取价', tone: 'muted' },
  live: { label: '实时', tone: 'success' },
  delayed: { label: '延迟', tone: 'warning' },
  close: { label: '收盘', tone: 'muted' },
  nav: { label: '净值', tone: 'success' },
  stale: { label: '已过期', tone: 'danger' },
  error: { label: '取价失败', tone: 'danger' },
}

export function quoteAge(quotedAt, now = Date.now()) {
  if (!quotedAt) return '无时间'
  const timestamp = new Date(quotedAt).getTime()
  if (!Number.isFinite(timestamp)) return '时间未知'
  const seconds = Math.max(0, Math.floor((Number(now) - timestamp) / 1000))
  if (seconds < 60) return `${seconds} 秒前`
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`
  return `${Math.floor(seconds / 86400)} 天前`
}

export function quoteTrust(item = {}, now = Date.now()) {
  const state = item.quote_state || item.state || 'unpriced'
  const meta = STATE_META[state] || { label: state, tone: 'muted' }
  return {
    state,
    label: meta.label,
    tone: meta.tone,
    age: quoteAge(item.quoted_at, now),
    actionable: Boolean(item.is_actionable),
    text: `${meta.label} · ${quoteAge(item.quoted_at, now)}`,
  }
}

export function monitoringTrust(status = {}) {
  if (!status.latest_cycle) return { tone: 'warning', title: '尚无监控周期', detail: '请手动刷新一次行情以建立可信基线。' }
  if (status.overdue) return { tone: 'danger', title: '监控已过期', detail: `行情覆盖 ${Number(status.quote_coverage_pct || 0).toFixed(0)}% · ${status.reason_code || 'monitoring_overdue'}` }
  if (['partial', 'failed', 'degraded'].includes(status.latest_cycle.status)) {
    return { tone: 'warning', title: '监控存在降级', detail: `最近周期 ${status.latest_cycle.status} · 行情覆盖 ${Number(status.quote_coverage_pct || 0).toFixed(0)}%` }
  }
  return { tone: 'success', title: '监控可信', detail: `行情覆盖 ${Number(status.quote_coverage_pct || 0).toFixed(0)}%` }
}
