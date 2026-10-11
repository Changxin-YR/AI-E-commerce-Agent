import { defineConfig } from '@tarojs/cli'

export default defineConfig({
  projectName: 'soloops-weapp',
  date: '2026-10-11',
  designWidth: 750,
  deviceRatio: { 640: 2.34 / 2, 750: 1, 828: 1.81 / 2 },
  sourceRoot: 'src',
  outputRoot: 'dist',
  framework: 'vue3',
  compiler: 'vite',
  plugins: ['@tarojs/plugin-platform-weapp'],
  // 后端地址在构建期内联，运行时不依赖 process 全局对象。
  defineConstants: {
    'process.env.TARO_APP_API_BASE': JSON.stringify(process.env.TARO_APP_API_BASE ?? ''),
  },
  mini: {},
})
