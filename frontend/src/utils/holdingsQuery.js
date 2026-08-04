// 持仓列表排序偏好：localStorage 记忆（先例：通知偏好），恢复时校验枚举防脏值。

export const HOLDINGS_SORT_KEY = 'holdings.sort'
export const HOLDINGS_SORTS = ['newest', 'name', 'risk']
export const DEFAULT_HOLDINGS_SORT = 'newest'

export function normalizeHoldingsSort(value) {
  return HOLDINGS_SORTS.includes(value) ? value : DEFAULT_HOLDINGS_SORT
}

export function loadHoldingsSort(storage = globalThis.localStorage) {
  try {
    return normalizeHoldingsSort(storage?.getItem(HOLDINGS_SORT_KEY))
  } catch {
    return DEFAULT_HOLDINGS_SORT
  }
}

export function saveHoldingsSort(sort, storage = globalThis.localStorage) {
  try {
    storage?.setItem(HOLDINGS_SORT_KEY, normalizeHoldingsSort(sort))
  } catch {
    // localStorage 不可用（隐私模式等）时排序偏好为尽力而为，不阻断列表
  }
}
