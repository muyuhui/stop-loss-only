import { stopLossRisk } from './format.js'

export function sortHoldingsByRisk(holdings = []) {
  return [...holdings].sort((left, right) => {
    if (left.status === 'triggered' && right.status !== 'triggered') return -1
    if (right.status === 'triggered' && left.status !== 'triggered') return 1
    const leftDistance = Number(left.stop_loss_distance_pct)
    const rightDistance = Number(right.stop_loss_distance_pct)
    return (Number.isFinite(leftDistance) ? leftDistance : Infinity) -
      (Number.isFinite(rightDistance) ? rightDistance : Infinity)
  })
}

export function dashboardRiskSummary(dashboard = {}) {
  const triggered = Number(dashboard.triggered_count) || 0
  const unread = Number(dashboard.active_alerts_count) || 0
  const near = (dashboard.holdings || []).filter(item => stopLossRisk(item.stop_loss_distance_pct, item.status).level === 'danger').length
  if (triggered > 0) return { level: 'danger', title: `${triggered} 个持仓已触发止损`, description: '请优先检查触发原因并决定是否平仓。' }
  if (near > 0) return { level: 'warning', title: `${near} 个持仓非常接近止损`, description: '价格波动可能很快触发止损，请保持关注。' }
  if (unread > 0) return { level: 'warning', title: `${unread} 条告警等待查看`, description: '组合当前没有新增触发持仓，请及时处理未读告警。' }
  return { level: 'safe', title: '当前组合风险平稳', description: '暂无触发或临近止损的持仓。' }
}
