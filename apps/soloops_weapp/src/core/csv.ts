/**
 * 大 CSV 分批导入的本机拆分（纯 TypeScript，不引入任何依赖）。
 * 与网页端 / Python 端 split 契约一致：soloops-split-v1 清单、按完整 CSV 记录拆分、
 * 每片 ≤ 2 MiB 且 ≤ 2000 条记录、最多 20 片、源文件 ≤ 40 MiB / 40000 条记录。
 */

import { sha256Hex } from './digest'

export interface CsvPart {
  filename: string
  sha256: string
  rows: number
  bytes: number
}

export interface CsvManifest {
  format: string
  source_filename: string
  source_sha256: string
  total_rows: number
  parts: CsvPart[]
}

export interface PreparedCsv {
  manifest: CsvManifest
  parts: Uint8Array[]
}

const PART_LIMIT = 2 * 1024 * 1024
const MAX_SOURCE_BYTES = 40 * 1024 * 1024
const MAX_ROWS = 40000
const MAX_PARTS = 20
const ROWS_PER_PART = 2000

/** 严格 UTF-8 解码；遇到非法序列抛错，不做替换猜测。 */
export function decodeUtf8(bytes: Uint8Array): string {
  const chunks: string[] = []
  let index = 0
  while (index < bytes.length) {
    const first = bytes[index]
    let codePoint: number
    let size: number
    if (first < 0x80) {
      codePoint = first
      size = 1
    } else if (first >= 0xc2 && first <= 0xdf) {
      codePoint = first & 0x1f
      size = 2
    } else if (first >= 0xe0 && first <= 0xef) {
      codePoint = first & 0x0f
      size = 3
    } else if (first >= 0xf0 && first <= 0xf4) {
      codePoint = first & 0x07
      size = 4
    } else {
      throw new Error('文件不是有效的 UTF-8；Excel 请先将目标工作表另存为 CSV UTF-8。')
    }
    if (index + size > bytes.length) {
      throw new Error('文件不是有效的 UTF-8；Excel 请先将目标工作表另存为 CSV UTF-8。')
    }
    for (let offset = 1; offset < size; offset += 1) {
      const next = bytes[index + offset]
      if ((next & 0xc0) !== 0x80) {
        throw new Error('文件不是有效的 UTF-8；Excel 请先将目标工作表另存为 CSV UTF-8。')
      }
      codePoint = (codePoint << 6) | (next & 0x3f)
    }
    chunks.push(String.fromCodePoint(codePoint))
    index += size
  }
  return chunks.join('')
}

/** UTF-8 编码（CSV 分片写盘与指纹计算共用）。 */
export function encodeUtf8(text: string): Uint8Array {
  const bytes: number[] = []
  for (const character of text) {
    const code = character.codePointAt(0) ?? 0
    if (code < 0x80) {
      bytes.push(code)
    } else if (code < 0x800) {
      bytes.push(0xc0 | (code >> 6), 0x80 | (code & 0x3f))
    } else if (code < 0x10000) {
      bytes.push(0xe0 | (code >> 12), 0x80 | ((code >> 6) & 0x3f), 0x80 | (code & 0x3f))
    } else {
      bytes.push(
        0xf0 | (code >> 18),
        0x80 | ((code >> 12) & 0x3f),
        0x80 | ((code >> 6) & 0x3f),
        0x80 | (code & 0x3f),
      )
    }
  }
  return Uint8Array.from(bytes)
}

function utf8Length(text: string): number {
  let length = 0
  for (const character of text) {
    const code = character.codePointAt(0) ?? 0
    length += code < 0x80 ? 1 : code < 0x800 ? 2 : code < 0x10000 ? 3 : 4
  }
  return length
}

function encodeRow(values: string[]): string {
  return `${values
    .map((value) =>
      /[,"\r\n]/.test(value) || (values.length === 1 && value === '')
        ? `"${value.replace(/"/g, '""')}"`
        : value,
    )
    .join(',')}\r\n`
}

/** 清单比对：格式、来源指纹、总记录数与每个分片均须一致。 */
export function sameManifest(left: CsvManifest | null, right: CsvManifest | null): boolean {
  if (left === null || right === null) return false
  for (const key of ['format', 'source_filename', 'source_sha256', 'total_rows'] as const) {
    if (left[key] !== right[key]) return false
  }
  if (left.parts.length !== right.parts.length) return false
  return left.parts.every((part, index) => {
    const other = right.parts[index]
    return (
      part.filename === other.filename &&
      part.sha256 === other.sha256 &&
      part.rows === other.rows &&
      part.bytes === other.bytes
    )
  })
}

/**
 * 拆分原始 CSV。抛出的错误文本与 Flutter 端保持一致，便于三端同一套提示。
 */
export function splitCsv(name: string, source: Uint8Array): PreparedCsv {
  if (!name.toLowerCase().endsWith('.csv')) {
    throw new Error('请选择 UTF-8 CSV；Excel 请先将目标工作表另存为 CSV UTF-8。')
  }
  if (source.length === 0 || source.length > MAX_SOURCE_BYTES) {
    throw new Error('源文件须非空且不超过 40 MiB。')
  }
  if ([...name].length > 240) throw new Error('文件名最多 240 字符。')

  const manifest: CsvManifest = {
    format: 'soloops-split-v1',
    source_filename: name,
    source_sha256: sha256Hex(source),
    total_rows: 0,
    parts: [],
  }
  const parts: Uint8Array[] = []
  let header = ''
  let columns = 0
  let count = 0
  let total = 0
  let output = ''

  const flush = (): void => {
    if (parts.length === MAX_PARTS) throw new Error('最多 20 个分片，请缩小来源范围。')
    const bytes = encodeUtf8(output)
    manifest.parts.push({
      filename: `part-${`${parts.length + 1}`.padStart(3, '0')}.csv`,
      sha256: sha256Hex(bytes),
      rows: count,
      bytes: bytes.length,
    })
    parts.push(bytes)
    output = header
    count = 0
  }

  const accept = (values: string[]): void => {
    if (header === '') {
      const names = values.map((value) => value.trim())
      if (
        names.length === 0 ||
        names.some((value) => value === '' || [...value].length > 120) ||
        new Set(names).size !== names.length
      ) {
        throw new Error('表头须非空且不重复，每列名称最多 120 字符。')
      }
      columns = names.length
      header = `\uFEFF${encodeRow(values)}`
      output += header
      return
    }
    if (values.length > columns) {
      throw new Error(`源数据记录 ${total + 1} 列数超出表头。`)
    }
    total += 1
    if (total > MAX_ROWS) throw new Error('最多 40000 个源记录，请缩小范围。')
    const row = encodeRow(values)
    if (utf8Length(header) + utf8Length(row) > PART_LIMIT) {
      throw new Error('单条记录超过 2 MiB，请修正原文件。')
    }
    if (count === ROWS_PER_PART || utf8Length(output) + utf8Length(row) > PART_LIMIT) {
      flush()
    }
    output += row
    count += 1
  }

  const parser = new CsvRecords(accept)
  parser.feed(decodeUtf8(source))
  parser.finish()
  if (count === 0) throw new Error('源文件须有表头和至少一个数据记录。')
  flush()
  manifest.total_rows = total
  return { manifest, parts }
}

/** 逐字符 CSV 记录解析器：支持引号、转义引号与多行字段。 */
class CsvRecords {
  constructor(private readonly accept: (values: string[]) => void) {}

  private state = 'start'
  private field = ''
  private row: string[] = []
  private length = 0
  private used = false
  private skipLf = false

  private append(character: string): void {
    this.length += 1
    if (character === '\u0000' || this.length > 2000) {
      throw new Error('单元格含无效字符或超过 2000 字符，请修正原文件。')
    }
    this.field += character
  }

  private endField(): void {
    this.row.push(this.field)
    if (this.row.length > 64) throw new Error('每条记录最多 64 列。')
    this.field = ''
    this.length = 0
    this.state = 'start'
  }

  private endRow(): void {
    if (this.used) this.endField()
    this.accept(this.row)
    this.row = []
    this.used = false
  }

  feed(text: string): void {
    for (const character of text) {
      if (this.skipLf) {
        this.skipLf = false
        if (character === '\n') continue
      }
      if (this.state === 'quoted') {
        if (character === '"') this.state = 'closed'
        else this.append(character)
        continue
      }
      if (this.state === 'closed' && character === '"') {
        this.append(character)
        this.state = 'quoted'
      } else if (character === '\r' || character === '\n') {
        this.skipLf = character === '\r'
        this.endRow()
      } else if (character === ',') {
        this.used = true
        this.endField()
      } else {
        if (this.state === 'closed') throw new Error('CSV 引号闭合后须为逗号或换行。')
        this.used = true
        if (this.state === 'start' && character === '"') {
          this.state = 'quoted'
        } else {
          this.append(character)
          this.state = 'plain'
        }
      }
    }
  }

  finish(): void {
    if (this.state === 'quoted') throw new Error('CSV 存在未闭合引号，请核对多行字段。')
    if (this.used) this.endRow()
  }
}

/** 校验外部导入的 manifest.json；字段或分片不合法时抛错。 */
export function validateManifest(value: unknown): CsvManifest {
  const record = value as Partial<CsvManifest> | null
  const fingerprint = /^[0-9a-f]{64}$/
  const parts = Array.isArray(record?.parts) ? record.parts : []
  if (
    record === null ||
    typeof record !== 'object' ||
    record.format !== 'soloops-split-v1' ||
    typeof record.source_filename !== 'string' ||
    record.source_filename === '' ||
    record.source_filename.length > 240 ||
    typeof record.source_sha256 !== 'string' ||
    !fingerprint.test(record.source_sha256) ||
    parts.length === 0 ||
    parts.length > MAX_PARTS ||
    typeof record.total_rows !== 'number' ||
    record.total_rows < 1 ||
    record.total_rows > MAX_ROWS
  ) {
    throw new Error('清单格式、指纹、总记录数或分片数无效。')
  }
  let total = 0
  const names = new Set<string>()
  const checked: CsvPart[] = parts.map((part) => {
    const candidate = part as Partial<CsvPart>
    if (
      typeof candidate?.filename !== 'string' ||
      candidate.filename.length > 120 ||
      !/^[^/\\]+\.csv$/.test(candidate.filename) ||
      names.has(candidate.filename) ||
      typeof candidate.sha256 !== 'string' ||
      !fingerprint.test(candidate.sha256) ||
      typeof candidate.rows !== 'number' ||
      candidate.rows < 1 ||
      candidate.rows > ROWS_PER_PART ||
      typeof candidate.bytes !== 'number' ||
      candidate.bytes < 1 ||
      candidate.bytes > PART_LIMIT
    ) {
      throw new Error('清单分片的文件名、记录数、大小或指纹无效。')
    }
    names.add(candidate.filename)
    total += candidate.rows
    return {
      filename: candidate.filename,
      sha256: candidate.sha256,
      rows: candidate.rows,
      bytes: candidate.bytes,
    }
  })
  if (total !== record.total_rows) throw new Error('分片记录总数与清单不一致。')
  return {
    format: record.format,
    source_filename: record.source_filename,
    source_sha256: record.source_sha256,
    total_rows: record.total_rows,
    parts: checked,
  }
}
