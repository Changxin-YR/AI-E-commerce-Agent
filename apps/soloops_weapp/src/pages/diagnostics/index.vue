<template>
  <view class="startup">
    <text class="title">环境信息</text>
    <text class="detail">{{ environment }}</text>
    <button :disabled="running" @tap="run">{{ running ? '验证中…' : '运行合成诊断' }}</button>
    <text class="detail">仅使用合成缓存、临时文件和剪贴板文本。</text>
    <text v-for="(value, key) in results" :key="key" class="detail">{{ key }}: {{ value }}</text>
    <button @tap="Taro.navigateBack()">返回启动页</button>
  </view>
</template>
<script setup lang="ts">
import { ref } from 'vue'
import Taro from '@tarojs/taro'
const device = Taro.getDeviceInfo()
const window = Taro.getWindowInfo()
const environment = `Taro 4 · Vue 3 · TypeScript\n平台：${device.platform}\n窗口：${window.windowWidth} × ${window.windowHeight}\n安全区：${window.safeArea?.top} / ${window.safeArea?.bottom}`
const results = ref<Record<string, string>>({})
const running = ref(false)
async function check(name: string, action: () => Promise<void>) {
  try { await action(); results.value[name] = 'PASS' }
  catch { results.value[name] = 'FAIL' }
  console.info('SOLOOPS_M0B', name, results.value[name])
}
async function run() {
  running.value = true
  const synthetic = 'SoloOps-M0B-synthetic'
  await check('cache', async () => {
    const key = `soloops_m0b_${Date.now()}`
    try {
      await Taro.setStorage({ key, data: synthetic })
      if ((await Taro.getStorage({ key })).data !== synthetic) throw new Error('cache')
    } finally { await Taro.removeStorage({ key }) }
  })
  await check('sandbox_file', async () => {
    const fs = Taro.getFileSystemManager()
    const path = `${Taro.env.USER_DATA_PATH}/soloops-m0b-${Date.now()}.txt`
    try {
      fs.writeFileSync(path, synthetic, 'utf8')
      if (fs.readFileSync(path, 'utf8') !== synthetic) throw new Error('file')
    } finally { fs.unlinkSync(path) }
  })
  await check('clipboard', async () => {
    await Taro.setClipboardData({ data: synthetic })
    if ((await Taro.getClipboardData()).data !== synthetic) throw new Error('clipboard')
  })
  running.value = false
}
</script>
