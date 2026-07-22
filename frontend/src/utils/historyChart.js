export const HISTORY_RANGES = [
  { value: '1m', label: '1月' },
  { value: '3m', label: '3月' },
  { value: '6m', label: '6月' },
  { value: '1y', label: '1年' },
]

export function historySummary(points = []) {
  if (!points.length) return null
  const prices = points.map(point => Number(point.price))
  return {
    latest: prices.at(-1),
    highest: Math.max(...prices),
    lowest: Math.min(...prices),
    stopLoss: Number(points.at(-1).stop_loss_price),
  }
}

export function buildHistoryChartOption(data, formatPrice) {
  const points = data?.points || []
  const dates = points.map(point => point.trade_date)
  const triggered = points.filter(point => point.triggered).map(point => ({
    coord: [point.trade_date, point.price], value: '触发',
  }))
  return {
    animationDuration: 350,
    color: ['#315f52', '#c34a3d'],
    grid: { left: 12, right: 18, top: 44, bottom: 42, containLabel: true },
    legend: { top: 4, left: 4, itemWidth: 18, textStyle: { color: '#59645f' }, data: ['价格', '止损线'] },
    tooltip: {
      trigger: 'axis',
      confine: true,
      formatter(params) {
        const index = params?.[0]?.dataIndex ?? 0
        const point = points[index]
        if (!point) return ''
        return `${point.trade_date}<br/>价格：${formatPrice(point.price)}<br/>止损：${formatPrice(point.stop_loss_price)}${point.triggered ? '<br/><strong>已触及止损线</strong>' : ''}`
      },
    },
    xAxis: { type: 'category', boundaryGap: false, data: dates, axisLabel: { hideOverlap: true, color: '#7a847f' } },
    yAxis: { type: 'value', scale: true, axisLabel: { formatter: value => formatPrice(value), color: '#7a847f' }, splitLine: { lineStyle: { color: '#edf0ee' } } },
    dataZoom: [{ type: 'inside', zoomOnMouseWheel: false, moveOnMouseMove: true }],
    series: [
      {
        name: '价格', type: 'line', data: points.map(point => point.price), showSymbol: points.length < 32,
        symbolSize: 5, smooth: 0.18, lineStyle: { width: 2.5 },
        markLine: {
          symbol: 'none', silent: true,
          label: { formatter: '买入价', color: '#6f7974' },
          lineStyle: { color: '#8a948f', type: 'dashed' },
          data: [{ yAxis: data?.buy_price }],
        },
        markPoint: {
          symbol: 'pin', symbolSize: 42, label: { formatter: '警' }, itemStyle: { color: '#c34a3d' }, data: triggered,
        },
      },
      {
        name: '止损线', type: 'line', data: points.map(point => point.stop_loss_price),
        step: data?.stop_loss_method === 'trailing' ? 'end' : false, showSymbol: false,
        lineStyle: { width: 2, type: 'dashed' },
        areaStyle: { color: 'rgba(195, 74, 61, 0.07)', origin: 'start' },
      },
    ],
  }
}
