import { describe, expect, it } from 'vitest'
import { apiEndpoint, normalizeApiOrigin } from '@/lib/apiEndpoint'

describe('Android API origin', () => {
  it('allows only the isolated emulator origin in local debug mode', () => {
    expect(apiEndpoint('/auth/session', true, 'http://10.0.2.2:8011', true)).toBe(
      'http://10.0.2.2:8011/api/auth/session',
    )
    expect(() => normalizeApiOrigin('http://10.0.2.2:8011')).toThrow()
  })
  it.each([
    'http://10.0.2.2:8000',
    'http://10.0.2.3:8011',
    'http://localhost:8011',
    'http://10.0.2.2:8011/api',
    'http://user@10.0.2.2:8011',
  ])('rejects debug origin outside the allowlist: %s', (origin) => {
    expect(() => normalizeApiOrigin(origin, true)).toThrow()
  })
  it('preserves browser same-origin routing', () => {
    expect(apiEndpoint('/auth/session', false)).toBe('/api/auth/session')
  })
  it('routes native requests and query strings to a fixed HTTPS origin', () => {
    expect(apiEndpoint('/shops?limit=10', true, ' https://ops.example.com/ ')).toBe(
      'https://ops.example.com/api/shops?limit=10',
    )
  })
  it.each([
    undefined,
    '',
    'invalid',
    'http://ops.example.com',
    'https://a:b@ops.example.com',
    'https://ops.example.com/api',
    'https://ops.example.com?q=x',
    'https://ops.example.com#token',
    'https://localhost',
    'https://127.0.0.1',
    'https://[::1]',
  ])('rejects unusable or ambiguous origin %s', (origin) => {
    expect(() => normalizeApiOrigin(origin)).toThrow()
  })
  it.each(['https://evil.example', '//evil.example', '/../../auth', '/%2e%2e/auth', '/\\evil'])(
    'rejects invalid API path %s',
    (path) => {
      expect(() => apiEndpoint(path, true, 'https://ops.example.com')).toThrow()
    },
  )
})
