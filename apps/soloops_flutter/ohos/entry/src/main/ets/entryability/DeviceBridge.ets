import { MethodCall, MethodCallHandler, MethodResult } from '@ohos/flutter_ohos';
import { common } from '@kit.AbilityKit';
import { asset } from '@kit.AssetStoreKit';
import { util } from '@kit.ArkTS';
import { BusinessError } from '@kit.BasicServicesKit';
import { preferences, uniformTypeDescriptor } from '@kit.ArkData';
import { fileIo as fs, fileUri, picker } from '@kit.CoreFileKit';
import { systemShare } from '@kit.ShareKit';

const FILE_LIMIT = 40 * 1024 * 1024;
const SESSION_ALIAS = 'soloops-device-session-v1';

class SessionPayload { baseUrl: string = ''; token: string = ''; }

export class DeviceBridge implements MethodCallHandler {
  private context: common.UIAbilityContext;
  private shareController: systemShare.ShareController | null = null;
  constructor(context: common.UIAbilityContext) { this.context = context; }

  onMethodCall(call: MethodCall, result: MethodResult): void {
    this.dispatch(call).then((value: Object | null) => result.success(value))
      .catch((error: BusinessError) => {
        // No credential, selected path or content is emitted to logs.
        result.error(`DEVICE_${error.code ?? 'FAILED'}`, '设备操作未完成，请重试', null);
      });
  }
  private query(): asset.AssetMap {
    const map: asset.AssetMap = new Map();
    map.set(asset.Tag.ALIAS, new util.TextEncoder().encodeInto(SESSION_ALIAS));
    return map;
  }
  private async readSession(): Promise<string | null> {
    const query = this.query(); query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL);
    try {
      const rows = await asset.query(query);
      if (rows.length !== 1) throw new Error('SESSION_RESULT');
      return util.TextDecoder.create('utf-8', { fatal: true }).decodeToString(rows[0].get(asset.Tag.SECRET) as Uint8Array);
    } catch (error) {
      if ((error as BusinessError).code === asset.ErrorCode.NOT_FOUND) return null;
      throw error as Error;
    }
  }
  private safeName(name: string): string {
    if (!name || name.length > 120 || /[\\/\x00-\x1f]/.test(name) || name === '.' || name === '..') throw new Error('FILE_NAME');
    return name;
  }
  private async pickFile(): Promise<Object | null> {
    const uris = await new picker.DocumentViewPicker(this.context).select({ maxSelectNumber: 1, fileSuffixFilters: ['报表|.csv,.xlsx'] });
    if (uris.length === 0) return null;
    if (uris.length !== 1 || !uris[0].startsWith('file://docs/')) throw new Error('FILE_URI');
    const file = fs.openSync(uris[0], fs.OpenMode.READ_ONLY);
    try {
      const size = fs.statSync(file.fd).size;
      if (size < 1 || size > FILE_LIMIT) throw new Error('FILE_SIZE');
      const bytes = new Uint8Array(size);
      let total = 0;
      while (total < size) {
        const buffer = new ArrayBuffer(Math.min(65536, size - total));
        const count = fs.readSync(file.fd, buffer, { offset: total, length: buffer.byteLength });
        if (count === 0) break;
        bytes.set(new Uint8Array(buffer, 0, count), total); total += count;
      }
      if (total !== size) throw new Error('FILE_CHANGED');
      return new Map<string, Object>([['name', new fileUri.FileUri(uris[0]).name], ['bytes', bytes], ['size', size]]);
    } finally { fs.closeSync(file); }
  }
  private writeFile(uri: string, bytes: Uint8Array): void {
    if (bytes.byteLength > FILE_LIMIT) throw new Error('FILE_SIZE');
    const file = fs.openSync(uri, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
    try {
      let offset = 0;
      while (offset < bytes.length) {
        const chunk = bytes.slice(offset, Math.min(offset + 65536, bytes.length));
        const count = fs.writeSync(file.fd, chunk.buffer);
        if (count <= 0) throw new Error('FILE_WRITE');
        offset += count;
      }
    } finally { fs.closeSync(file); }
  }
  private async dispatch(call: MethodCall): Promise<Object | null> {
    switch (call.method) {
      case 'sessionRead': return this.readSession();
      case 'sessionWrite': {
        const value = call.argument('value') as string;
        if (value.length > 4096) throw new Error('SESSION_SIZE');
        const payload = JSON.parse(value) as SessionPayload;
        if (!/^https?:\/\//.test(payload.baseUrl) || !/^[A-Za-z0-9_-]{32,128}$/.test(payload.token)) throw new Error('SESSION_FORMAT');
        const data: asset.AssetMap = new Map(); data.set(asset.Tag.SECRET, new util.TextEncoder().encodeInto(value));
        if (await this.readSession() !== null) await asset.update(this.query(), data);
        else {
          data.set(asset.Tag.ALIAS, new util.TextEncoder().encodeInto(SESSION_ALIAS));
          data.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_UNLOCKED);
          data.set(asset.Tag.SYNC_TYPE, asset.SyncType.NEVER);
          await asset.add(data);
        }
        return null;
      }
      case 'sessionClear': {
        try { await asset.remove(this.query()); }
        catch (error) { if ((error as BusinessError).code !== asset.ErrorCode.NOT_FOUND) throw error as Error; }
        return null;
      }
      case 'settingsRead': {
        const pref = await preferences.getPreferences(this.context, { name: 'soloops_settings' });
        const result = new Map<string, Object>();
        if (await pref.has('baseUrl')) result.set('baseUrl', await pref.get('baseUrl', '') as string);
        if (await pref.has('shopId')) result.set('shopId', await pref.get('shopId', 0) as number);
        return result;
      }
      case 'settingsWrite': {
        const baseUrl = call.argument('baseUrl') as string;
        if (baseUrl.length > 2048 || !/^https?:\/\//.test(baseUrl)) throw new Error('SERVICE_ADDRESS');
        const pref = await preferences.getPreferences(this.context, { name: 'soloops_settings' });
        await pref.put('baseUrl', baseUrl);
        await pref.put('shopId', call.argument('shopId') as number); await pref.flush(); return null;
      }
      case 'pickFile': return this.pickFile();
      case 'saveFile': {
        const name = this.safeName(call.argument('name') as string);
        const bytes = call.argument('bytes') as Uint8Array;
        if (bytes.byteLength > FILE_LIMIT) throw new Error('FILE_SIZE');
        const uris = await new picker.DocumentViewPicker(this.context).save({ newFileNames: [name] });
        if (uris.length === 0) return false;
        if (uris.length !== 1 || !uris[0].startsWith('file://docs/')) throw new Error('FILE_URI');
        this.writeFile(uris[0], bytes); return true;
      }
      case 'shareFile': {
        const name = this.safeName(call.argument('name') as string);
        const path = `${this.context.cacheDir}/share-${name}`;
        this.writeFile(path, call.argument('bytes') as Uint8Array);
        const data = new systemShare.SharedData({ utd: uniformTypeDescriptor.UniformDataType.FILE, uri: fileUri.getUriFromPath(path), title: name });
        this.shareController = new systemShare.ShareController(data);
        this.shareController.on('dismiss', () => { if (fs.accessSync(path)) fs.unlinkSync(path); });
        await this.shareController.show(this.context, { selectionMode: systemShare.SelectionMode.SINGLE });
        return null;
      }
      default: throw new Error('METHOD_UNSUPPORTED');
    }
  }
}
