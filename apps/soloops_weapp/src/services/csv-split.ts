import { sha256 } from '@noble/hashes/sha256'
import { CsvRecords } from './csv-records.ts'
import type { ImportManifest } from './import-types'

// Mini-programs do not guarantee TextEncoder, TextDecoder, File or Web Crypto.
export function utf8(text: string): Uint8Array {
  const encoded = encodeURIComponent(text)
  const bytes: number[] = []
  for (let i = 0; i < encoded.length; i++) {
    if (encoded[i] === '%') { bytes.push(parseInt(encoded.slice(i + 1, i + 3), 16)); i += 2 }
    else bytes.push(encoded.charCodeAt(i))
  }
  return new Uint8Array(bytes)
}
export class Utf8Decoder {
  private pending: number[] = []
  decode(bytes: Uint8Array, final = false): string {
    const all = [...this.pending, ...bytes]
    let end = all.length
    if (!final && end) {
      let start = end - 1
      while (start >= 0 && (all[start]! & 0xc0) === 0x80) start--
      const first = all[start] ?? 0
      const width = first < 0x80 ? 1 : first < 0xe0 ? 2 : first < 0xf0 ? 3 : 4
      if (start >= 0 && end - start < width) end = start
    }
    this.pending = all.slice(end)
    try { return decodeURIComponent(all.slice(0, end).map(byte => `%${byte.toString(16).padStart(2, '0')}`).join('')) }
    catch { throw new Error('CSV 须为有效 UTF-8 编码，请另存为 CSV UTF-8。') }
  }
}
function encodeRow(values: string[]): Uint8Array {
  return utf8(values.map(value => /[,"\r\n]/.test(value) || (values.length === 1 && value === '') ? `"${value.replace(/"/g, '""')}"` : value).join(',') + '\r\n')
}
function concat(chunks: Uint8Array[]): Uint8Array {
  const result = new Uint8Array(chunks.reduce((n, chunk) => n + chunk.length, 0))
  let offset = 0
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length }
  return result
}
const hex = (bytes: Uint8Array) => Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
export function sameManifest(a: ImportManifest, b: ImportManifest): boolean {
  return a.format === b.format && a.source_filename === b.source_filename && a.source_sha256 === b.source_sha256 && a.total_rows === b.total_rows && a.parts.length === b.parts.length && a.parts.every((p, i) => { const q = b.parts[i]; return q && p.filename === q.filename && p.sha256 === q.sha256 && p.rows === q.rows && p.bytes === q.bytes })
}
export async function splitCsv(source: { name: string; size: number }, read: (offset: number, size: number) => Promise<Uint8Array>, write: (name: string, bytes: Uint8Array) => Promise<void>, progress: (rows: number) => void = () => {}): Promise<ImportManifest> {
  if (!/\.csv$/i.test(source.name) || !source.size || source.size > 40 * 1024 * 1024 || Array.from(source.name).length > 240) throw new Error('请选择不超过 40 MiB 的非空 UTF-8 CSV，文件名最多 240 字符。')
  const manifest: ImportManifest = { format: 'soloops-split-v1', source_filename: source.name, source_sha256: '', total_rows: 0, parts: [] }
  const parser = new CsvRecords(), decoder = new Utf8Decoder(), hash = sha256.create()
  let header: Uint8Array | undefined, columns = 0, chunks: Uint8Array[] = [], size = 0, rows = 0
  async function flush() {
    if (manifest.parts.length >= 20) throw new Error('最多 20 片，请按业务范围重新导出。')
    const bytes = concat(chunks), filename = `part-${String(manifest.parts.length + 1).padStart(3, '0')}.csv`
    await write(filename, bytes)
    manifest.parts.push({ filename, bytes: bytes.length, rows, sha256: hex(sha256(bytes)) })
    chunks = [header!]; size = header!.length; rows = 0
  }
  async function accept(values: string[]) {
    if (!header) {
      const names = values.map(v => v.trim())
      if (!names.length || names.some(v => !v || Array.from(v).length > 120) || new Set(names).size !== names.length) throw new Error('表头须非空、不重复且每列不超过 120 字符。')
      columns = names.length; header = concat([new Uint8Array([239, 187, 191]), encodeRow(values)])
      chunks = [header]; size = header.length; return
    }
    if (values.length > columns) throw new Error(`记录 ${manifest.total_rows + 1} 列数超出表头。`)
    if (++manifest.total_rows > 40000) throw new Error('最多 40000 个逻辑记录。')
    const bytes = encodeRow(values)
    if (header.length + bytes.length > 2097152) throw new Error('单条记录超过 2 MiB。')
    if (rows === 2000 || size + bytes.length > 2097152) await flush()
    chunks.push(bytes); size += bytes.length; rows++
  }
  for (let offset = 0; offset < source.size; offset += 65536) {
    const length = Math.min(65536, source.size - offset), bytes = await read(offset, length)
    if (bytes.length !== length) throw new Error('源文件读取不完整，请重新选择。')
    hash.update(bytes)
    let text = decoder.decode(bytes, offset + length === source.size)
    if (offset === 0) text = text.replace(/^\uFEFF/, '')
    for (const values of parser.feed(text)) await accept(values)
    progress(manifest.total_rows)
  }
  for (const values of parser.finish()) await accept(values)
  if (!rows) throw new Error('文件须有表头和至少一个数据记录。')
  await flush(); manifest.source_sha256 = hex(hash.digest()); return manifest
}
