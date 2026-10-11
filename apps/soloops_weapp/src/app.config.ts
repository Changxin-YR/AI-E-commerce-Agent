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
    // 第三波（R2 财务细分）：订单账单核对 / 费用映射规则。
    'pages/order_reconciliation/index',
    'pages/fee_rules/index',
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
  // 图标为 src/assets/tabbar 下的 81×81 单色 PNG，构建时由 Taro 按 iconPath 复制到包内同名路径。
  tabBar: {
    color: '#56736a',
    selectedColor: '#315c52',
    backgroundColor: '#ffffff',
    borderStyle: 'black',
    list: [
      {
        pagePath: 'pages/home/index',
        text: '首页',
        iconPath: 'assets/tabbar/home.png',
        selectedIconPath: 'assets/tabbar/home-active.png',
      },
      {
        pagePath: 'pages/tasks/index',
        text: '待办',
        iconPath: 'assets/tabbar/tasks.png',
        selectedIconPath: 'assets/tabbar/tasks-active.png',
      },
      {
        pagePath: 'pages/agent/index',
        text: 'AI',
        iconPath: 'assets/tabbar/agent.png',
        selectedIconPath: 'assets/tabbar/agent-active.png',
      },
      {
        pagePath: 'pages/support/index',
        text: '客服',
        iconPath: 'assets/tabbar/support.png',
        selectedIconPath: 'assets/tabbar/support-active.png',
      },
      {
        pagePath: 'pages/mine/index',
        text: '我的',
        iconPath: 'assets/tabbar/mine.png',
        selectedIconPath: 'assets/tabbar/mine-active.png',
      },
    ],
  },
})
