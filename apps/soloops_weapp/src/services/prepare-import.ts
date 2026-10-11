import Taro from '@tarojs/taro'
import { splitCsv } from './csv-split'
import type { LocalFile } from './files'
import type { ImportManifest } from './import-types'

export interface PreparedImport {
  manifest: ImportManifest
  files: LocalFile[]
  dispose: () => void
}
export async function prepareImport(
  file: LocalFile,
  progress: (rows: number) => void,
): Promise<PreparedImport> {
  const fs = Taro.getFileSystemManager()
  const folder = `${Taro.env.USER_DATA_PATH}/soloops-import-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  fs.mkdirSync(folder)
  const dispose = () => {
    try {
      fs.rmdirSync(folder, true)
    } catch {
      /* Already released. */
    }
  }
  const files: LocalFile[] = []
  try {
    const manifest = await splitCsv(
      file,
      (position, length) =>
        new Promise((resolve, reject) =>
          fs.readFile({
            filePath: file.path,
            position,
            length,
            success: (result) =>
              resolve(new Uint8Array(result.data as ArrayBuffer)),
            fail: reject,
          }),
        ),
      async (name, bytes) => {
        const path = `${folder}/${name}`
        await new Promise<void>((resolve, reject) =>
          fs.writeFile({
            filePath: path,
            data: bytes.buffer as ArrayBuffer,
            success: () => resolve(),
            fail: reject,
          }),
        )
        files.push({ path, name, size: bytes.length })
      },
      progress,
    )
    return { manifest, files, dispose }
  } catch (error) {
    dispose()
    throw error
  }
}
