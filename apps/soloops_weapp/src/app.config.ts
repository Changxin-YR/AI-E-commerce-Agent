export default defineAppConfig({
  // 首页必须是 pages 的第一项，也是 tabBar 的第一项。
  pages: [
    'pages/home/index',
    'pages/tasks/index',
    'pages/agent/index',
    'pages/support/index',
    'pages/mine/index',
    'pages/login/index',
    'pages/imports/index',
    'pages/listings/index',
    'pages/inventory/index',
    'pages/index/index',
    'pages/diagnostics/index',
  ],
  window: {
    navigationBarTitleText: 'SoloOps',
    navigationBarBackgroundColor: '#f4f7f5',
    navigationBarTextStyle: 'black',
    backgroundColor: '#f4f7f5',
  },
  // 5 大入口：首页 / 待办 / AI / 客服 / 我的（与契约 entries 一致）。
  tabBar: {
    color: '#56736a',
    selectedColor: '#315c52',
    backgroundColor: '#ffffff',
    borderStyle: 'black',
    list: [
      { pagePath: 'pages/home/index', text: '首页' },
      { pagePath: 'pages/tasks/index', text: '待办' },
      { pagePath: 'pages/agent/index', text: 'AI' },
      { pagePath: 'pages/support/index', text: '客服' },
      { pagePath: 'pages/mine/index', text: '我的' },
    ],
  },
})
