export function holdingStatusLabel(status) {
  return { holding: '持有中', triggered: '已触发', closed: '已关闭' }[status] || status
}

export function holdingStatusTag(status) {
  return { holding: 'success', triggered: 'danger', closed: 'info' }[status] || 'info'
}
