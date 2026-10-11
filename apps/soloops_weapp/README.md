# SoloOps 微信小程序最小工程

Taro 4.3.0、Vue 3.5.43、TypeScript 5.9.3，Node 24.16.0 / npm 11.13.0。
采用 Taro Vite runner 4.3.0 的 Vite 4 peer 依赖组合：Vite 4.5.14、
`@vitejs/plugin-vue` 4.6.2、`@vitejs/plugin-vue-jsx` 3.1.0。
`package-lock.json` 锁定解析结果，CI 用 `npm ci`。

```sh
cd apps/soloops_weapp
npm ci
npm run type-check
npm run build:weapp
npm audit --json
```

编译目录为 `dist/`。微信开发者工具导入本目录（`project.config.json` 指向 `dist/`）。
`touristappid` 仅为本地工程占位，真实 AppID 和私有工具配置由开发者本机提供。
合法域名校验保持启用；本页没有网络、登录、上传或 AI 调用。
开发工具加载和模拟器运行必须单独验收，编译成功不代表已在工具内运行。

当前 npm 审计仍失败，详见 [`依赖审查`](../../docs/mobile/dependency-review.md)。
这些问题阻止生产发布放行；本阶段只记录最小编译可行性。不可对审计建议直接使用
`--force` 将 Taro 降级到 1.x/3.x，或把 Vite 升至不满足 peer 约束的版本。
