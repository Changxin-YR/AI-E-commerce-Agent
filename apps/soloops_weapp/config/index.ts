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
  mini: {},
})
