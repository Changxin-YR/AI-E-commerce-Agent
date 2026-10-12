// Compare the service output models with the client DTOs the WeChat pages parse.
//
//   python scripts/mobile/dump_schema_fields.py > fields.json   (from backend/)
//   node scripts/mobile/check_schema_fields.mjs fields.json
//
// A response field that the client DTO does not declare would be silently
// dropped by the page, so that direction fails the check. Client-only fields are
// reported as notes: a few pages intentionally flatten nested output.
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(dirname(fileURLToPath(import.meta.url))))
const servicesDir = join(root, 'apps', 'soloops_weapp', 'src', 'services')

// Response model -> client interface. Most names match; the rest are the client
// side names chosen by the pages (mail DTOs, schedule rows, review wrappers) or
// a flattened summary that keeps only the fields the page renders.
const aliases = {
  AuthorizationOutput: 'AuthorizationGrant',
  ChannelOutput: 'MailChannel',
  MailOutput: 'OutboundMail',
  OccurrenceOutput: 'Occurrence',
  OrderReviewCurrent: 'ReviewCurrent',
  OrderReviewPreview: 'ReviewPreview',
  OrderReviewSaved: 'ReviewSaved',
  ScheduleOutput: 'ScheduleRow',
}

export function interfaceFields(source, name) {
  const match = source.match(
    new RegExp(
      `export interface ${name}(?: extends [^{]+)? \\{([\\s\\S]*?)\\n\\}`,
    ),
  )
  if (!match) return null
  return [...match[1].matchAll(/^\s{2}([a-z_][a-z0-9_]*)\??:/gm)].map(
    (field) => field[1],
  )
}

// `export interface X extends Y` keeps the inherited fields out of X's own
// block, so the declared set has to walk the `extends` chain.
export function declaredFields(sources, name, seen = new Set()) {
  if (seen.has(name)) return []
  seen.add(name)
  const entry = sources.find((candidate) =>
    interfaceFields(candidate.body, name),
  )
  if (!entry) return null
  const own = interfaceFields(entry.body, name)
  const parents = entry.body.match(
    new RegExp(`export interface ${name} extends ([^{]+)\\{`),
  )
  const inherited = parents
    ? parents[1]
        .split(',')
        .map((parent) => parent.trim())
        .flatMap((parent) => declaredFields(sources, parent, seen) || [])
    : []
  return [...new Set([...own, ...inherited])]
}

export function compare(fields, sources) {
  const problems = []
  const notes = []
  for (const [model, keys] of Object.entries(fields).sort()) {
    const name = aliases[model] || model
    const declared = declaredFields(sources, name)
    if (!declared) {
      problems.push(`${model} 在客户端 DTO 中找不到接口 ${name}`)
      continue
    }
    const missing = keys.filter((key) => !declared.includes(key))
    if (missing.length)
      problems.push(`${model} 客户端缺少字段：${missing.join(', ')}`)
    const extra = declared.filter((key) => !keys.includes(key))
    if (extra.length) notes.push(`${model} 客户端多出字段：${extra.join(', ')}`)
  }
  return { problems, notes }
}

function loadSources() {
  return readdirSync(servicesDir)
    .filter((file) => file.endsWith('.ts'))
    .map((file) => ({
      file,
      body: readFileSync(join(servicesDir, file), 'utf8'),
    }))
}

function main() {
  const path = process.argv[2]
  if (!path) {
    console.error(
      '用法：node scripts/mobile/check_schema_fields.mjs <fields.json>',
    )
    return 1
  }
  const fields = JSON.parse(readFileSync(path, 'utf8'))
  const { problems, notes } = compare(fields, loadSources())
  for (const note of notes) console.log(`提示：${note}`)
  for (const problem of problems) console.error(problem)
  console.log(
    `响应模型 ${Object.keys(fields).length} 个，字段 ${Object.values(fields).reduce((sum, keys) => sum + keys.length, 0)} 个`,
  )
  if (problems.length) return 1
  console.log('PASS: 客户端 DTO 覆盖服务端响应字段')
  return 0
}

if (process.argv[1] && process.argv[1].endsWith('check_schema_fields.mjs'))
  process.exit(main())
