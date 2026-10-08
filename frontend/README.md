# SoloOps 前端

Vue 3 + TypeScript + Vue Router，构建工具为 Vite。完整安装与启动步骤见 [项目 README](../README.md)。

- `src/views`：页面数据组织。
- `src/components`：可复用表单、布局和反馈。
- `src/api`：HTTP 与错误处理。
- `src/composables`：会话状态，不在 localStorage 保存令牌。
- `src/styles`：设计变量与样式。
- `src/__tests__`、`e2e`：单元测试与连接真实测试 API 的浏览器测试。

日常命令：`npm run dev`、`npm run lint`、`npm run build`、`npm run test:unit`、`npm run test:e2e`。浏览器测试使用隔离 MySQL 数据库，须先完成根目录的测试环境配置。
