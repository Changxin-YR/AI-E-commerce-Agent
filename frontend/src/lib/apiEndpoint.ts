/** Native builds have a fixed HTTPS API origin, separate from bundled UI assets. */
export function normalizeApiOrigin(value: string | undefined): string {
  if (!value?.trim()) throw new Error('安卓应用尚未配置服务地址，请联系管理员。')
  let url: URL
  try {
    url = new URL(value.trim())
  } catch {
    throw new Error('服务地址必须是有效的 HTTPS 地址。')
  }
  if (
    url.protocol !== 'https:' ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    url.pathname !== '/'
  ) {
    throw new Error('服务地址必须使用 HTTPS，且不包含账号、路径或查询参数。')
  }
  if (['localhost', '127.0.0.1', '[::1]'].includes(url.hostname)) {
    throw new Error('安卓应用需要可访问的服务地址，不能使用本机回环地址。')
  }
  return url.origin
}

export function apiEndpoint(path: string, native: boolean, origin?: string): string {
  if (!path.startsWith('/') || path.startsWith('//') || path.includes('\\')) {
    throw new Error('无效的业务接口路径。')
  }
  const prefix = native ? normalizeApiOrigin(origin) : ''
  const target = `${prefix}/api${path}`
  const parsed = new URL(target, 'https://localhost')
  if (!parsed.pathname.startsWith('/api/')) throw new Error('业务接口路径超出允许范围。')
  return target
}
