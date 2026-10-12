// Compare the pages directory with app.config.ts registrations and weapp routes.
// Pages without a registration are never compiled by Taro and would be missing
// from dist/, so the check fails on both directions.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = dirname(dirname(fileURLToPath(import.meta.url)))
const pagesDir = join(root, 'src', 'pages')
const config = readFileSync(join(root, 'src', 'app.config.ts'), 'utf8')
const navigation = readFileSync(
  join(root, 'src', 'services', 'navigation.ts'),
  'utf8',
)
const registered = new Set(
  [...config.matchAll(/'pages\/([^/']+)\/index'/g)].map((match) => match[1]),
)
const present = readdirSync(pagesDir).filter((name) => {
  const dir = join(pagesDir, name)
  if (!statSync(dir).isDirectory()) return false
  return readdirSync(dir).includes('index.vue')
})
const missing = present.filter((name) => !registered.has(name))
const unknown = [...registered].filter((name) => !present.includes(name))
const routes = new Set(
  [...navigation.matchAll(/'(\/[a-z-]*)':\s*'\/pages\/([^/']+)\/index'/g)].map(
    (match) => `${match[1]} -> ${match[2]}`,
  ),
)
// System pages are reached from the seller home rather than a business route.
const systemPages = new Set([
  'index',
  'settings',
  'diagnostics',
  'workbench',
  'operations',
])
const unlinked = present.filter(
  (name) =>
    !systemPages.has(name) &&
    ![...routes].some((route) => route.endsWith(` ${name}`)),
)
for (const name of missing) console.error(`未注册页面：pages/${name}/index`)
for (const name of unknown)
  console.error(`配置指向不存在的页面：pages/${name}/index`)
for (const name of unlinked) console.error(`缺少业务路由：pages/${name}/index`)
console.log(
  `页面 ${present.length} 个，已注册 ${registered.size} 个，业务路由 ${routes.size} 条`,
)
if (missing.length || unknown.length || unlinked.length) process.exit(1)
console.log('PASS: 页面注册与路由映射一致')
