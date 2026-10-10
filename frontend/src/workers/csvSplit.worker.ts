import { splitCsv } from '@/lib/csvSplit'

self.onmessage = async (event: MessageEvent<File>) => {
  try {
    const result = await splitCsv(event.data, (progress) => self.postMessage({ progress }))
    self.postMessage({ result })
  } catch (cause) {
    self.postMessage({
      error: cause instanceof Error ? cause.message : '无法完成本机拆分，请重新选择原文件。',
    })
  }
}
