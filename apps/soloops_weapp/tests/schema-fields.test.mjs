import test from 'node:test'
import assert from 'node:assert/strict'
import {
  compare,
  declaredFields,
  interfaceFields,
} from '../../../scripts/mobile/check_schema_fields.mjs'

const sources = [
  {
    file: 'sample.ts',
    body: `export interface Parent {
  id: number
  created_at: string
}
export interface Child extends Parent {
  result: string
}
export interface Page {
  items: Child[]
  next_before_id: number | null
}
`,
  },
]

test('interface fields include the extends chain', () => {
  assert.deepEqual(interfaceFields(sources[0].body, 'Child'), ['result'])
  assert.deepEqual(declaredFields(sources, 'Child'), [
    'result',
    'id',
    'created_at',
  ])
  assert.deepEqual(declaredFields(sources, 'Page'), ['items', 'next_before_id'])
  assert.equal(declaredFields(sources, 'Missing'), null)
})

test('compare fails only when the response field is undeclared', () => {
  const fields = {
    Child: ['id', 'created_at', 'result'],
    Page: ['items', 'next_before_id'],
  }
  assert.deepEqual(compare(fields, sources), { problems: [], notes: [] })

  const missing = compare(
    { Child: ['id', 'created_at', 'result', 'note'] },
    sources,
  )
  assert.equal(missing.problems.length, 1)
  assert.match(missing.problems[0], /客户端缺少字段：note/)

  const extra = compare(
    { Child: ['id', 'created_at', 'result'], Page: ['items'] },
    sources,
  )
  assert.match(extra.notes.join(), /Page 客户端多出字段：next_before_id/)
  assert.deepEqual(extra.problems, [])

  const unknown = compare({ Unknown: ['id'] }, sources)
  assert.match(unknown.problems.join(), /找不到接口 Unknown/)
})
