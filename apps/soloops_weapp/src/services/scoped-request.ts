import { ApiError, type ApiClient } from './client.ts'

// The API client guards account/shop changes; pages also guard their own lifetime.
export function scopedRequest(
  api: Pick<ApiClient, 'request'>,
  context: () => unknown,
) {
  return async function request<T>(
    ...args: Parameters<ApiClient['request']>
  ): Promise<T> {
    const token = context()
    if (token == null) throw new ApiError('页面已关闭。', 0, 'stale_response')
    const result = await api.request<T>(...args)
    if (context() !== token)
      throw new ApiError('页面上下文已切换。', 0, 'stale_response')
    return result
  }
}
