export function priceInputMeta(assetType) {
  return assetType === 'fund'
    ? { precision: 3, step: 0.001, min: 0.001 }
    : { precision: 2, step: 0.01, min: 0.01 }
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
