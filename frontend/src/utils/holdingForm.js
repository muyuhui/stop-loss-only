export function priceInputMeta(assetType) {
  return assetType === 'fund'
    ? { precision: 3, step: 0.001, min: 0.001 }
    : { precision: 2, step: 0.01, min: 0.01 }
}

function localDateString(date = new Date()) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * 把新仓试算结果映射为稳定持仓新增表单的预填值。
 * 数量向下取整为整数份，买入价按资产精度取整；输入无效返回 null。
 */
export function holdingPrefillFromPlan(result) {
  const input = result?.normalized_input
  if (!input || !result) return null
  const code = String(input.code ?? '').trim()
  const name = String(input.name ?? '').trim()
  const type = input.asset_type === 'fund' ? 'fund' : 'stock'
  const entryPrice = Number(input.entry_price)
  const recommended = Number(result.recommended_quantity)
  const stopValue = Number(input.stop_value)
  const stopMethod = ['fixed', 'percentage', 'trailing'].includes(input.stop_method) ? input.stop_method : null
  if (
    !code || !name || !Number.isFinite(entryPrice) || entryPrice <= 0
    || !Number.isFinite(recommended) || recommended <= 0
    || !Number.isFinite(stopValue) || stopValue <= 0 || !stopMethod
  ) return null
  const precision = priceInputMeta(type).precision
  const factor = 10 ** precision
  const quantity = Math.floor(recommended)
  if (quantity < 1) return null
  return {
    code,
    name,
    type,
    buy_price: Math.round(entryPrice * factor) / factor,
    quantity,
    buy_date: localDateString(),
    stop_loss_method: stopMethod,
    stop_loss_value: stopValue,
  }
}

export function stopLossInputMeta(method, assetType = 'stock') {
  if (method === 'fixed') {
    const price = priceInputMeta(assetType)
    return { unit: '元', ...price, help: `达到这个价格时触发止损，例如 ${assetType === 'fund' ? '1.050' : '9.00'}。` }
  }
  if (method === 'trailing') return { unit: '%', precision: 1, step: 0.1, min: 0.1, help: '从持仓后的最高价回落该比例时触发，例如 10%。' }
  return { unit: '%', precision: 1, step: 0.1, min: 0.1, help: '相对买入价下跌该比例时触发，例如 10%。' }
}

export function holdingPayload(form) {
  return {
    ...form,
    code: form.code.trim(),
    name: form.name.trim(),
    buy_price: Number(form.buy_price),
    quantity: Number(form.quantity),
    stop_loss_value: Number(form.stop_loss_value),
  }
}
