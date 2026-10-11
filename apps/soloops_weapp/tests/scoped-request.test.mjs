import test from 'node:test'
import assert from 'node:assert/strict'
import { scopedRequest } from '../src/services/scoped-request.ts'

test('page requests reject late results after unload or context replacement', async () => {
  for (const next of [null, 2]) {
    let context = 1,
      resolve
    const request = scopedRequest(
      {
        request: () =>
          new Promise((r) => {
            resolve = r
          }),
      },
      () => context,
    )
    const result = request('/example')
    context = next
    resolve({ private: 'old page' })
    await assert.rejects(result, (error) => error.code === 'stale_response')
  }
})

test('closed pages cannot issue writes; active pages keep payload and result', async () => {
  let context = null,
    calls = []
  const request = scopedRequest(
    {
      request: async (...args) => {
        calls.push(args)
        return 42
      },
    },
    () => context,
  )
  await assert.rejects(request('/example', 'POST', { version: 2 }))
  assert.equal(calls.length, 0)
  context = 1
  assert.equal(await request('/example', 'POST', { version: 2 }), 42)
  assert.deepEqual(calls, [['/example', 'POST', { version: 2 }]])
})
