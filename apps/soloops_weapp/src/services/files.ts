import Taro from '@tarojs/taro'
import { api } from './session'

export interface LocalFile { path: string; name: string; size: number }
export async function chooseFile(): Promise<LocalFile> {
  const result = await Taro.chooseMessageFile({ count: 1, type: 'file', extension: ['csv', 'xlsx'] })
  const file = result.tempFiles[0]
  if (!file) throw new Error('尚未选择文件。')
  return { path: file.path, name: file.name, size: file.size }
}
export function uploadFile<T>(shopId: number, file: LocalFile, options: Record<string, string | number>): Promise<T> {
  if (!file.size || file.size > 2097152) throw new Error('每片文件须非空且不超过 2 MiB。大 CSV 请使用分片导入。')
  const query = Object.entries({ ...options, filename: file.name }).map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join('&')
  return api.request<T>(`/shops/${shopId}/imports/multipart?${query}`, 'POST', undefined, true, async request => {
    const { 'Content-Type': _type, ...header } = request.header
    const result = await Taro.uploadFile({ url: request.url, filePath: file.path, name: 'file', header, timeout: request.timeout })
    let data: unknown
    try { data = JSON.parse(result.data) } catch { data = null }
    if (result.statusCode >= 200 && result.statusCode < 300 && !data) throw new Error('无法读取上传结果，请回查批次。')
    return { statusCode: result.statusCode, data }
  })
}
export async function exportFile(path: string, filename: string): Promise<void> {
  const local = await api.request<string>(path, 'GET', undefined, true, async request => {
    const result = await Taro.downloadFile({ url: request.url, header: request.header, timeout: request.timeout })
    return { statusCode: result.statusCode, data: result.tempFilePath }
  })
  await Taro.shareFileMessage({ filePath: local, fileName: filename })
}
