/**
 * 表单事件取值：Taro 组件事件的 detail 类型在不同组件间不一致，
 * 这里统一收敛为字符串，避免各页面重复断言。
 */

export function inputValue(event: unknown): string {
  const detail = (event as { detail?: { value?: unknown } } | null | undefined)?.detail
  const value = detail?.value
  if (value === null || value === undefined) return ''
  return `${value}`
}

/** 选择器（selector / date / time）返回的下标或字面值。 */
export function pickerValue(event: unknown): string {
  return inputValue(event)
}
