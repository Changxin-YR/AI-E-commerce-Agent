// Verify the seller home exposes every business route and that each page still
// consumes the query keys the backend emits. A link key that no page reads
// would silently drop the linked record.
//
// The backend publishes these keys in backend/app/services/workbench.py (LINKS
// plus the R0/R1/R2 defaults) and backend/app/services/operations.py
// (_destinations). `return_task` is not listed as a page key: operations opens
// destinations with navigateTo, so the mini-program page stack itself returns to
// the task and no page needs to parse it.
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const read = (...parts) => readFileSync(join(root, ...parts), 'utf8')

// Key: page directory; value: query keys published for that page. `task` marks
// the pages the operations destinations prefix with shop/identity/channel.
// `context` lists keys those pages accept but do not filter on.
const task = ['shop', 'identity', 'channel']
const matrix = {
  '/': { dir: 'operations', own: ['task', 'run'], home: false },
  '/agent': {
    dir: 'agent',
    own: [
      'shop',
      'execution',
      'authorization',
      'run',
      'mode',
      'product',
      'message',
    ],
  },
  '/imports': { dir: 'imports', own: [...task, 'batch', 'kind'] },
  '/listings': {
    dir: 'listings',
    own: ['shop', 'listing', 'product'],
    context: ['identity', 'channel'],
  },
  '/support': {
    dir: 'support',
    own: ['shop', 'draft', 'message'],
    context: ['identity', 'channel'],
  },
  '/inventory': { dir: 'inventory', own: [...task, 'sku'] },
  '/analytics': {
    dir: 'analytics',
    own: [...task, 'analysis', 'start_at', 'end_at', 'currency', 'sku'],
  },
  '/overview': { dir: 'overview', own: ['shop', 'report'] },
  '/outbound': { dir: 'outbound', own: ['shop', 'mail'] },
  '/profit': { dir: 'profit', own: ['shop', 'study'] },
  '/expenses': { dir: 'expenses', own: ['shop', 'expense', 'rule'] },
  '/statements': { dir: 'statements', own: ['shop', 'review'] },
  '/order-reconciliation': {
    dir: 'order-reconciliation',
    own: ['shop', 'data_identity', 'channel'],
  },
  '/settlements': { dir: 'settlements', own: ['shop', 'settlement'] },
  '/rules': { dir: 'rules', own: ['shop', 'version', 'identity', 'channel'] },
  '/schedules': {
    dir: 'schedules',
    own: ['shop', 'plan', 'identity', 'channel'],
  },
  '/product-quality': {
    dir: 'product-quality',
    own: ['shop', 'report', 'sku_prefix', 'identity', 'channel'],
  },
  '/product-edits': {
    dir: 'product-edits',
    own: ['shop', 'edit', 'identity', 'channel'],
  },
}

const problems = []
const navigation = read('src', 'services', 'navigation.ts')
const home = read('src', 'pages', 'index', 'index.vue')

for (const [route, entry] of Object.entries(matrix)) {
  const page = read('src', 'pages', entry.dir, 'index.vue')
  if (!/useLoad\(/.test(page))
    problems.push(`${route} 未在 useLoad 中接收深链参数`)
  for (const key of entry.own)
    if (!page.includes(key)) problems.push(`${route} 未处理深链键 ${key}`)
  if (!navigation.includes(`'${route}':`))
    problems.push(`navigation.ts 缺少路由 ${route}`)
  if (entry.home !== false && !home.includes(`/pages/${entry.dir}/index`))
    problems.push(`卖家首页缺少入口 ${route}`)
}

// Operations and workbench render backend links; they must forward the path and
// query they receive instead of hard-coding a page.
const operations = read('src', 'pages', 'operations', 'index.vue')
const workbench = read('src', 'pages', 'workbench', 'index.vue')
if (!/openLink\(path, query\)/.test(operations))
  problems.push('operations 页未按后端 destination 转发 path/query')
if (!/destinations/.test(operations))
  problems.push('operations 页未展示待办 destinations')
if (!/openLink\(path, query\)/.test(workbench))
  problems.push('workbench 页未按工作项 link 转发 path/query')
const serviceImport = "import { openLink } from '../../services/navigation'"
for (const [name, source] of [
  ['operations', operations],
  ['workbench', workbench],
])
  if (!source.includes(serviceImport))
    problems.push(`${name} 页未使用统一导航服务`)

for (const problem of problems) console.error(problem)
console.log(
  `深链矩阵 ${Object.keys(matrix).length} 条路由，检查键 ${Object.values(matrix).reduce((sum, item) => sum + item.own.length, 0)} 个`,
)
if (problems.length) process.exit(1)
console.log('PASS: 五入口与业务深链矩阵一致')
