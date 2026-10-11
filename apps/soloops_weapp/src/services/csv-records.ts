// Matches csv.reader(strict=True): only a quote at field start opens quoting.
// State survives byte blocks, including CRLF and escaped quotes across boundaries.
export class CsvRecords {
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
    if (this.row.length > 64)
      throw new Error('每条记录最多64列，请移除无关列。')
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
        if (this.state === 'closed')
          throw new Error('CSV引号闭合后须为逗号或换行，请重新导出。')
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
    if (this.state === 'quoted')
      throw new Error('CSV存在未闭合引号，请核对多行字段。')
    return this.used ? [this.endRow()] : []
  }
}
