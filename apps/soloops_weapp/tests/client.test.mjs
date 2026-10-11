import test from 'node:test'
import assert from 'node:assert/strict'
import { ApiClient, normalizeServer } from '../src/services/client.ts'
const loginResponse = {
  statusCode: 200,
  data: {
    access_token: 'synthetic-token',
    user_id: 1,
    username: 'seller',
    session_id: 'test',
    client_type: 'weapp',
    expires_at: new Date(Date.now() + 600000).toISOString(),
  },
}
const deferred = () => {
  let resolve
  const promise = new Promise((r) => {
    resolve = r
  })
  return { promise, resolve }
}

test('file transport shares authentication, scope invalidation and current 401 handling', async () => {
  const client = new ApiClient(async () => loginResponse)
  await client.login('https://example.com', 'seller', 'secret')
  const pending = deferred()
  const request = client.request(
    '/shops/1/imports/multipart',
    'POST',
    undefined,
    true,
    async (options) => {
      assert.equal(options.header.Authorization, 'Bearer synthetic-token')
      return pending.promise
    },
  )
  client.invalidateScope()
  pending.resolve({ statusCode: 201, data: { id: 1 } })
  await assert.rejects(request, (error) => error.code === 'stale_response')
  let expired = false
  client.onExpired = () => {
    expired = true
  }
  await assert.rejects(
    client.request(
      '/imports/1/errors.csv',
      'GET',
      undefined,
      true,
      async () => ({ statusCode: 401, data: null }),
    ),
    (error) => error.status === 401,
  )
  assert.equal(expired, true)
})
test('HTTPS server normalization rejects embedded credentials and query strings', () => {
  assert.equal(
    normalizeServer(' https://example.com/api/ '),
    'https://example.com',
  )
  for (const address of [
    'http://example.com',
    'https://a@b.com',
    'https://a.com?token=x',
    'https://a.com/#x',
    '//a.com',
  ])
    assert.throws(() => normalizeServer(address))
})
test('login preserves password spaces, omits authorization, and returns no token', async () => {
  const calls = []
  const client = new ApiClient(async (o) => {
    calls.push(o)
    return loginResponse
  })
  const session = await client.login(
    'https://example.com',
    ' seller ',
    ' password ',
  )
  assert.equal(calls[0].data.password, ' password ')
  assert.equal(calls[0].data.username, 'seller')
  assert.equal(calls[0].data.client_type, 'weapp')
  assert.equal(calls[0].header.Authorization, undefined)
  assert.equal(session.access_token, undefined)
  await client.request('/shops')
  assert.equal(calls[1].header.Authorization, 'Bearer synthetic-token')
})
test('requests require an active session', async () => {
  let calls = 0
  const client = new ApiClient(async () => {
    calls++
    return loginResponse
  })
  await assert.rejects(client.request('/shops'), (e) => e.status === 401)
  assert.equal(calls, 0)
})
test('401 expires session once and removes bearer credentials', async () => {
  let expired = 0
  const client = new ApiClient(async (o) =>
    o.url.endsWith('/login')
      ? loginResponse
      : {
          statusCode: 401,
          data: { error: { message: '过期', code: 'expired' } },
        },
  )
  client.onExpired = () => {
    expired++
  }
  await client.login('https://example.com', 'seller', 'secret')
  await assert.rejects(
    client.request('/shops'),
    (e) => e.status === 401 && e.message === '过期',
  )
  assert.equal(expired, 1)
  await assert.rejects(client.request('/shops'), (e) => e.status === 401)
})
test('shop switch invalidates in-flight data and stale 401 cannot expire current scope', async () => {
  const pending = deferred()
  let expired = 0
  const client = new ApiClient(async (o) =>
    o.url.endsWith('/login') ? loginResponse : pending.promise,
  )
  client.onExpired = () => {
    expired++
  }
  await client.login('https://example.com', 'seller', 'secret')
  const request = client.request('/shops/1/inventory')
  client.invalidateScope()
  pending.resolve({ statusCode: 401, data: {} })
  await assert.rejects(request, (e) => e.code === 'stale_response')
  assert.equal(expired, 0)
})
test('older login cannot overwrite a newer account', async () => {
  const pending = deferred()
  let count = 0
  const client = new ApiClient(async () =>
    ++count === 1 ? pending.promise : loginResponse,
  )
  const old = client.login('https://old.example.com', 'old', 'secret')
  await client.login('https://new.example.com', 'new', 'secret')
  pending.resolve(loginResponse)
  await assert.rejects(old, (e) => e.code === 'stale_response')
})
test('conflicts remain explicit and are never automatically retried', async () => {
  let calls = 0
  const client = new ApiClient(async (o) => {
    calls++
    return o.url.endsWith('/login')
      ? loginResponse
      : {
          statusCode: 409,
          data: { error: { message: '版本已变化', code: 'conflict' } },
        }
  })
  await client.login('https://example.com', 'seller', 'secret')
  await assert.rejects(
    client.request('/profile', 'PUT', { version: 0 }),
    (e) => e.status === 409 && e.message === '版本已变化',
  )
  assert.equal(calls, 2)
})
test('logout all uses the revocation endpoint and clears local credentials on success', async () => {
  const calls = []
  const client = new ApiClient(async (o) => {
    calls.push(o)
    return o.url.endsWith('/login')
      ? loginResponse
      : { statusCode: 204, data: '' }
  })
  await client.login('https://example.com', 'seller', 'secret')
  await client.logout(true)
  assert.equal(calls[1].url, 'https://example.com/api/mobile/auth/logout-all')
  await assert.rejects(client.request('/shops'), (e) => e.status === 401)
})
test('network failure provides a retryable error without revealing credentials', async () => {
  const client = new ApiClient(async (o) => {
    if (o.url.endsWith('/login')) return loginResponse
    throw new Error('secret')
  })
  await client.login('https://example.com', 'seller', 'secret')
  await assert.rejects(
    client.request('/shops'),
    (e) => e.code === 'network_error' && !e.message.includes('secret'),
  )
})
