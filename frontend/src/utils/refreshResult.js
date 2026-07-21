export function summarizeRefresh(result) {
  const failed = (result.items || []).filter(item => item.error || !item.fresh)
  if (result.status === 'partial' || failed.length) {
    return { type: 'warning', message: `部分刷新失败或行情已过期：${failed.map(item => item.code).join('、')}` }
  }
  if ((result.triggered || []).length) {
    return { type: 'warning', message: `止损触发: ${result.triggered.map(item => item.name).join('、')}` }
  }
  return { type: 'success', message: '价格刷新完成' }
}
