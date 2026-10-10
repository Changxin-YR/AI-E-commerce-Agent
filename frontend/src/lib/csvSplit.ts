import type { ImportManifest } from '@/types/imports'

export const SOURCE_LIMIT = 40 * 1024 * 1024
const PART_LIMIT = 2 * 1024 * 1024
const BLOCK_SIZE = 65536
export interface PreparedImport {
  manifest: ImportManifest
  files: File[]
}
export interface SplitProgress {
  bytes: number
  totalBytes: number
  rows: number
}

// Matches csv.reader(strict=True): only a quote at field start opens quoting.
// State survives byte blocks, including CRLF and escaped quotes across boundaries.
class CsvRecords {
  private state: 'start' | 'plain' | 'quoted' | 'closed' = 'start'
  private field = ''
  private length = 0
  private row: string[] = []
  private used = false
  private skipLf = false

  private append(char: string): void {
    if (char === '\0' || ++this.length > 2000)
      throw new Error('单元格含无效控制字符或超过2000字符，请修正原文件。')
    this.field += char
  }
  private endField(): void {
    this.row.push(this.field)
    if (this.row.length > 64) throw new Error('每条记录最多64列，请移除无关列。')
    this.field = ''
    this.length = 0
    this.state = 'start'
  }
  private endRow(): string[] {
    if (this.used) this.endField()
    const result = this.row
    this.row = []
    this.used = false
    return result
  }
  *feed(text: string): Generator<string[]> {
    for (const char of text) {
      if (this.skipLf) {
        this.skipLf = false
        if (char === '\n') continue
      }
      if (this.state === 'quoted') {
        if (char === '"') this.state = 'closed'
        else this.append(char)
        continue
      }
      if (this.state === 'closed' && char === '"') {
        this.append(char)
        this.state = 'quoted'
      } else if (char === '\r' || char === '\n') {
        this.skipLf = char === '\r'
        yield this.endRow()
      } else if (char === ',') {
        this.used = true
        this.endField()
      } else {
        if (this.state === 'closed') throw new Error('CSV引号闭合后须为逗号或换行，请重新导出。')
        this.used = true
        if (this.state === 'start' && char === '"') this.state = 'quoted'
        else {
          this.append(char)
          this.state = 'plain'
        }
      }
    }
  }
  finish(): string[][] {
    if (this.state === 'quoted') throw new Error('CSV存在未闭合引号，请核对多行字段。')
    return this.used ? [this.endRow()] : []
  }
}

function encodeRow(values: string[]): Uint8Array<ArrayBuffer> {
  const encoded = values.map((value) =>
    /[,"\r\n]/.test(value) || (values.length === 1 && value === '')
      ? `"${value.replace(/"/g, '""')}"`
      : value,
  )
  return new TextEncoder().encode(`${encoded.join(',')}\r\n`)
}
async function digest(blob: Blob): Promise<string> {
  // Web Crypto has no incremental digest; callers cap the source/part before this read.
  const hash = await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())
  return Array.from(new Uint8Array(hash), (byte) => byte.toString(16).padStart(2, '0')).join('')
}

export function sameManifest(left: ImportManifest, right: ImportManifest): boolean {
  return (
    left.format === right.format &&
    left.source_filename === right.source_filename &&
    left.source_sha256 === right.source_sha256 &&
    left.total_rows === right.total_rows &&
    left.parts.length === right.parts.length &&
    left.parts.every((part, index) => {
      const other = right.parts[index]
      return (
        other &&
        part.filename === other.filename &&
        part.sha256 === other.sha256 &&
        part.rows === other.rows &&
        part.bytes === other.bytes
      )
    })
  )
}

export async function splitCsv(
  source: File,
  progress: (value: SplitProgress) => void = () => {},
): Promise<PreparedImport> {
  if (!/\.csv$/i.test(source.name))
    throw new Error('请选择UTF-8 CSV；Excel请先将目标工作表另存为CSV UTF-8。')
  if (!source.size || source.size > SOURCE_LIMIT)
    throw new Error('源文件须非空且不超过40 MiB；请按明确日期或业务范围重新导出。')
  if (Array.from(source.name).length > 240) throw new Error('文件名最多240字符，请缩短后重试。')
  if (!crypto.subtle)
    throw new Error('当前环境无法校验文件指纹，请使用HTTPS或本机地址，或联系管理员协助拆分。')
  progress({ bytes: 0, totalBytes: source.size, rows: 0 })
  const manifest: ImportManifest = {
    format: 'soloops-split-v1',
    source_filename: source.name,
    source_sha256: await digest(source),
    total_rows: 0,
    parts: [],
  }
  const files: File[] = []
  let header: Uint8Array<ArrayBuffer> | undefined
  let columns = 0
  let chunks: Uint8Array<ArrayBuffer>[] = []
  let bytes = 0
  let count = 0
  async function flush(): Promise<void> {
    if (files.length === 20) throw new Error('最多20个分片，请按明确范围重新导出。')
    const filename = `part-${String(files.length + 1).padStart(3, '0')}.csv`
    const file = new File(chunks, filename, { type: 'text/csv' })
    manifest.parts.push({ filename, bytes: file.size, rows: count, sha256: await digest(file) })
    files.push(file)
    chunks = [header!]
    bytes = header!.byteLength
    count = 0
  }
  async function accept(values: string[]): Promise<void> {
    if (!header) {
      const names = values.map((value) => value.trim())
      if (
        !names.length ||
        names.some((name) => !name || Array.from(name).length > 120) ||
        new Set(names).size !== names.length
      )
        throw new Error('表头须非空且不重复，每列名称最多120字符。')
      columns = names.length
      header = new Uint8Array([0xef, 0xbb, 0xbf, ...encodeRow(values)])
      chunks = [header]
      bytes = header.byteLength
      return
    }
    if (values.length > columns)
      throw new Error(`源数据记录${manifest.total_rows + 1}列数超出表头。`)
    if (++manifest.total_rows > 40000)
      throw new Error('最多40000个源数据记录，请按明确范围重新导出。')
    const row = encodeRow(values)
    if (header.byteLength + row.byteLength > PART_LIMIT)
      throw new Error('单条记录超过2 MiB，请修正原文件。')
    if (count === 2000 || bytes + row.byteLength > PART_LIMIT) await flush()
    chunks.push(row)
    bytes += row.byteLength
    count++
  }
  const decoder = new TextDecoder('utf-8', { fatal: true })
  const parser = new CsvRecords()
  for (let offset = 0; offset < source.size; offset += BLOCK_SIZE) {
    const end = Math.min(offset + BLOCK_SIZE, source.size)
    let text: string
    try {
      text = decoder.decode(await source.slice(offset, end).arrayBuffer(), {
        stream: end < source.size,
      })
    } catch {
      throw new Error('CSV须为UTF-8编码（可带BOM），请核对中文后另存为CSV UTF-8。')
    }
    for (const row of parser.feed(text)) await accept(row)
    progress({ bytes: end, totalBytes: source.size, rows: manifest.total_rows })
  }
  for (const row of parser.finish()) await accept(row)
  if (!count) throw new Error('源文件须有表头和至少一个数据记录。')
  await flush()
  return { manifest, files }
}
