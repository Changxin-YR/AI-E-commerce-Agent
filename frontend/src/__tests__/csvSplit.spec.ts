// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import path from 'node:path'
import { splitCsv, sameManifest, SOURCE_LIMIT } from '@/lib/csvSplit'

const python = path.resolve(
  '../backend/.venv',
  process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const oracle = `
import base64, json, sys, tempfile
from pathlib import Path
from app.services.import_split import split_csv
data = json.load(sys.stdin)
with tempfile.TemporaryDirectory(prefix='soloops-csv-contract-') as folder:
    source = Path(folder) / 'synthetic.csv'
    source.write_bytes(base64.b64decode(data['source']))
    destination = Path(folder) / 'parts'
    manifest = split_csv(source, destination)
    print(json.dumps({'manifest': manifest.model_dump(), 'parts': [base64.b64encode((destination / part.filename).read_bytes()).decode() for part in manifest.parts]}))
`
async function compareToPython(content: string): Promise<void> {
  const input = Buffer.from(content)
  const expected = JSON.parse(
    execFileSync(python, ['-c', oracle], {
      cwd: path.resolve('../backend'),
      input: JSON.stringify({ source: input.toString('base64') }),
      maxBuffer: 20 * 1024 * 1024,
    }).toString(),
  )
  const result = await splitCsv(new File([input], 'synthetic.csv'))
  expect(result.manifest).toEqual(expected.manifest)
  for (const [index, file] of result.files.entries()) {
    const bytes = Buffer.from(await file.arrayBuffer())
    expect(bytes.toString('base64')).toBe(expected.parts[index])
    expect(createHash('sha256').update(bytes).digest('hex')).toBe(
      result.manifest.parts[index]?.sha256,
    )
  }
}

describe('bounded browser CSV contract', () => {
  it.each([2001, 10001])('matches Python bytes, rows and SHA256 for %i records', async (count) => {
    expect.hasAssertions()
    await compareToPython(
      '\ufeffsku,name,facts\r\n' +
        Array.from(
          { length: count },
          (_, i) => `S${i},"合成,商品","首行\r\n末行""引用"""\r\n`,
        ).join(''),
    )
  })
  it('matches Python for empty, escaped, short and mixed newline records', async () => {
    expect.hasAssertions()
    await compareToPython(
      'sku,name,facts\nA,"双""引号",x\rB,😀,x\r\n\nC\nD,,\nE,x"y,z\nF,"a\rb\nc\r\nd",末行',
    )
    await compareToPython('value\n""\n\n"尾行"')
  })
  it('splits on encoded byte size and preserves multibyte chunk boundaries', async () => {
    expect.hasAssertions()
    await compareToPython(
      '\ufeffsku,name,facts\r\n' +
        Array.from({ length: 650 }, (_, i) => `S${i},合成,"首行\n${'字'.repeat(1800)}"\r\n`).join(
          '',
        ),
    )
  })
  it.each([
    '',
    'sku,sku\na,b\n',
    'sku,name\na,"bad\n',
    'sku,name\na,"x"wrong\n',
    'sku,name\na,\0\n',
    'sku,name\na,' + 'a'.repeat(2001),
    Array.from({ length: 65 }, (_, i) => `h${i}`).join(',') + '\nx',
    'sku,name\na,b,c',
    'sku,name\n' + 'A,B\n'.repeat(40001),
  ])('rejects unsafe or out-of-bounds content without a partial result %#', async (content) => {
    await expect(splitCsv(new File([content], 'synthetic.csv'))).rejects.toThrow()
  })
  it('refuses invalid UTF8, wrong extension and source bytes over 40MiB', async () => {
    await expect(splitCsv(new File([new Uint8Array([0xff])], 'bad.csv'))).rejects.toThrow('UTF-8')
    await expect(splitCsv(new File(['a,b\nx,y'], 'bad.xlsx'))).rejects.toThrow('CSV')
    await expect(splitCsv(new File([new Uint8Array(SOURCE_LIMIT + 1)], 'big.csv'))).rejects.toThrow(
      '40 MiB',
    )
  })
  it('matches the manifest only when every source and part field is identical', async () => {
    const { manifest } = await splitCsv(new File(['sku\nA'], 'synthetic.csv'))
    expect(sameManifest(manifest, structuredClone(manifest))).toBe(true)
    expect(sameManifest(manifest, { ...manifest, source_sha256: 'a'.repeat(64) })).toBe(false)
    expect(
      sameManifest(manifest, { ...manifest, parts: [{ ...manifest.parts[0]!, bytes: 3 }] }),
    ).toBe(false)
  })
  it('accepts exactly 40000 records in 20 row-bounded parts', async () => {
    const result = await splitCsv(new File(['sku\n' + 'A\n'.repeat(40000)], 'synthetic.csv'))
    expect(result.manifest.total_rows).toBe(40000)
    expect(result.files).toHaveLength(20)
    expect(result.manifest.parts.every((part) => part.rows === 2000 && part.bytes <= 2097152)).toBe(
      true,
    )
  })
  it('rejects normalized output requiring more than 20 byte-bounded parts', async () => {
    // Literal quotes in an unquoted field are doubled by the compatible writer.
    const source = new File(
      ['sku\n' + ('A' + '"'.repeat(1900) + '\n').repeat(11050)],
      'synthetic.csv',
    )
    expect(source.size).toBeLessThan(SOURCE_LIMIT)
    await expect(splitCsv(source)).rejects.toThrow('最多20个分片')
  }, 20000)
})
