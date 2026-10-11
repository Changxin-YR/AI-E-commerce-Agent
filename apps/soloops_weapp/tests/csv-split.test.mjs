import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import {
  splitCsv,
  utf8,
  Utf8Decoder,
  sameManifest,
} from '../src/services/csv-split.ts'

async function split(text) {
  const bytes = new TextEncoder().encode(text),
    files = []
  const manifest = await splitCsv(
    { name: 'source.csv', size: bytes.length },
    async (offset, length) => bytes.slice(offset, offset + length),
    async (name, content) => files.push({ name, content }),
  )
  return { manifest, files, bytes }
}
test('UTF-8 decoding survives byte boundaries and rejects invalid encoding', () => {
  const text = '中文😀a',
    bytes = utf8(text),
    decoder = new Utf8Decoder()
  assert.deepEqual(bytes, new TextEncoder().encode(text))
  let result = ''
  for (let i = 0; i < bytes.length; i++)
    result += decoder.decode(bytes.slice(i, i + 1), i === bytes.length - 1)
  assert.equal(result, text)
  for (const invalid of [[0xc0, 0x80], [0xff], [0xed, 0xa0, 0x80], [0xe4]])
    assert.throws(() => new Utf8Decoder().decode(new Uint8Array(invalid), true))
})
test('quoted newlines and doubled quotes stay in one logical record; hashes match Node', async () => {
  const { manifest, files, bytes } = await split(
    '\ufeffsku,name\r\na,"line 1\r\nline ""2"""\r\nb,中文😀\r\n',
  )
  assert.equal(manifest.total_rows, 2)
  assert.equal(
    manifest.source_sha256,
    createHash('sha256').update(bytes).digest('hex'),
  )
  assert.equal(
    manifest.parts[0].sha256,
    createHash('sha256').update(files[0].content).digest('hex'),
  )
  assert.match(
    new TextDecoder().decode(files[0].content),
    /line 1\r\nline ""2""/,
  )
})
test('splits at 2000 data records and repeats header', async () => {
  const { manifest, files } = await split(
    'sku,name\n' +
      Array.from({ length: 2001 }, (_, i) => `${i},产品`).join('\n'),
  )
  assert.deepEqual(
    manifest.parts.map((p) => p.rows),
    [2000, 1],
  )
  assert.match(
    new TextDecoder().decode(files[1].content),
    /^sku,name\r\n2000,产品/,
  )
  assert.equal(sameManifest(manifest, structuredClone(manifest)), true)
  assert.equal(
    sameManifest(manifest, { ...manifest, source_sha256: 'changed' }),
    false,
  )
})
test('rejects malformed CSV, duplicated headers and empty source', async () => {
  for (const text of [
    'sku,sku\na,b',
    'sku,name\na,"unterminated',
    'sku\na,b',
    'sku\n',
    '',
  ])
    await assert.rejects(split(text))
})
test('byte ceiling creates smaller parts before 2000 rows', async () => {
  const { manifest } = await split(
    'sku,name\n' +
      Array.from({ length: 1500 }, (_, i) => `${i},${'中'.repeat(1000)}`).join(
        '\n',
      ),
  )
  assert.ok(manifest.parts.length > 1)
  assert.ok(manifest.parts.every((p) => p.bytes <= 2097152 && p.rows <= 2000))
  assert.equal(manifest.total_rows, 1500)
})
