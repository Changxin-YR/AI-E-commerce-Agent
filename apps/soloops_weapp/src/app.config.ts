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
    // 第二波（R2 业务）：经营分析 / 经营概览 / 利润 / 费用 / 账单 / 结算 /
    // 经营规则 / 对外邮件 / 计划任务 / 商品质量 / 商品批量修订。
    'pages/analytics/index',
    'pages/overview/index',
    'pages/profit/index',
    'pages/expenses/index',
    'pages/statements/index',
    'pages/settlements/index',
    'pages/rules/index',
    'pages/outbound/index',
    'pages/schedules/index',
    'pages/product_quality/index',
    'pages/product_edits/index',
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
