import { MethodCall, MethodCallHandler, MethodResult } from '@ohos/flutter_ohos';
import { common } from '@kit.AbilityKit';
import { asset } from '@kit.AssetStoreKit';
import { BusinessError } from '@kit.BasicServicesKit';
import { util } from '@kit.ArkTS';
import { preferences } from '@kit.ArkData';
import { fileIo as fs, fileUri, picker } from '@kit.CoreFileKit';
import { cryptoFramework } from '@kit.CryptoArchitectureKit';
import { uniformTypeDescriptor } from '@kit.ArkData';
import { systemShare } from '@kit.ShareKit';
import { DEBUG } from 'BuildProfile';

const LIMIT = 2 * 1024 * 1024;
const ALIAS = 'soloops-m0-synthetic';
const CACHE = 'soloops_m0_nonsensitive';
const TEXT = 'SoloOps M0 synthetic file\n';

class ProbeError extends Error {
  public code: string;
  constructor(code: string) { super(code); this.code = code; }
}

// Debug-only system capability POC. Asset errors propagate; there is no plaintext fallback.
export class M0Bridge implements MethodCallHandler {
  private controller: systemShare.ShareController | null = null;
  private selectedUri: string | null = null;
  private context: common.UIAbilityContext;
  constructor(context: common.UIAbilityContext) { this.context = context; }

  onMethodCall(call: MethodCall, result: MethodResult): void {
    if (!DEBUG) { result.error('DEBUG_ONLY', 'M0 probe unavailable', null); return; }
    this.dispatch(call).then((value: Object | null) => result.success(value))
      .catch((error: BusinessError) => {
        const code = error instanceof ProbeError ? error.code : `NATIVE_${error.code}`;
        console.info(`SOLOOPS_M0_NATIVE ${call.method} ${code}`);
        result.error(String(code), 'System capability rejected the operation', null);
      });
  }

  private encode(value: string): Uint8Array { return new util.TextEncoder().encodeInto(value); }
  private query(alias: string = ALIAS): asset.AssetMap {
    const query: asset.AssetMap = new Map();
    query.set(asset.Tag.ALIAS, this.encode(alias));
    return query;
  }
  private async readAsset(): Promise<string | null> {
    const query = this.query();
    query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ALL);
    try {
      const rows = await asset.query(query);
      if (rows.length !== 1) throw new ProbeError('ASSET_RESULT');
      return util.TextDecoder.create('utf-8', { fatal: true })
        .decodeToString(rows[0].get(asset.Tag.SECRET) as Uint8Array);
    } catch (error) {
      if ((error as BusinessError).code === asset.ErrorCode.NOT_FOUND) return null;
      throw error as Error;
    }
  }
  private async clearAsset(): Promise<boolean> {
    try { await asset.remove(this.query()); }
    catch (error) {
      if ((error as BusinessError).code !== asset.ErrorCode.NOT_FOUND) throw error as Error;
    }
    return true;
  }
  private async writeAsset(value: string): Promise<boolean> {
    if (!value.startsWith('m0-synthetic-') || value.length > 128) throw new ProbeError('SYNTHETIC_ONLY');
    const secret: asset.AssetMap = new Map();
    secret.set(asset.Tag.SECRET, this.encode(value));
    if (await this.readAsset() !== null) {
      await asset.update(this.query(), secret);
    } else {
      secret.set(asset.Tag.ALIAS, this.encode(ALIAS));
      secret.set(asset.Tag.ACCESSIBILITY, asset.Accessibility.DEVICE_UNLOCKED);
      secret.set(asset.Tag.SYNC_TYPE, asset.SyncType.NEVER);
      // IS_PERSISTENT defaults to false; setting it explicitly requires a privileged permission.
      await asset.add(secret);
    }
    return true;
  }
  private scope(call: MethodCall): string {
    const scope = call.argument('scope') as string;
    if (scope !== 'synthetic-a' && scope !== 'synthetic-b') throw new ProbeError('INVALID_SCOPE');
    return scope;
  }
  private async clearShare(): Promise<boolean> {
    const path = `${this.context.cacheDir}/soloops-m0-share.txt`;
    if (fs.accessSync(path)) fs.unlinkSync(path);
    this.controller = null;
    return !fs.accessSync(path);
  }
  private async pick(): Promise<Object> {
    const uris = await new picker.DocumentViewPicker(this.context).select({
      maxSelectNumber: 1, fileSuffixFilters: ['Text|.txt']
    });
    if (uris.length === 0) return new Map<string, Object>([['status', 'cancelled']]);
    if (uris.length !== 1 || !uris[0].startsWith('file://docs/')) throw new ProbeError('DOCUMENT_URI_REQUIRED');
    this.selectedUri = uris[0];
    try { return await this.readSelectedUri(uris[0]); }
    finally { this.selectedUri = null; }
  }
  private async readSelectedUri(uri: string): Promise<Object> {
    if (uri !== this.selectedUri) throw new ProbeError('DOCUMENT_NOT_SELECTED');
    const file = fs.openSync(uri, fs.OpenMode.READ_ONLY);
    try {
      if (fs.statSync(file.fd).size > LIMIT) throw new ProbeError('FILE_TOO_LARGE');
      const bytes = new Uint8Array(LIMIT + 1);
      let total = 0;
      while (total <= LIMIT) {
        const chunk = new ArrayBuffer(Math.min(65536, LIMIT + 1 - total));
        const count = fs.readSync(file.fd, chunk, { offset: total, length: chunk.byteLength });
        if (count === 0) break;
        bytes.set(new Uint8Array(chunk, 0, count), total);
        total += count;
        if (total > LIMIT) throw new ProbeError('FILE_TOO_LARGE');
      }
      const content = bytes.slice(0, total);
      const name = new fileUri.FileUri(uri).name;
      const type = uniformTypeDescriptor.getUniformDataTypeByFilenameExtension('.' + name.split('.').pop());
      const mime = uniformTypeDescriptor.getTypeDescriptor(type).mimeTypes;
      const digest = cryptoFramework.createMd('SHA256');
      await digest.update({ data: content });
      const hash = (await digest.digest()).data;
      return new Map<string, Object>([
        ['status', 'selected'], ['name', name], ['scheme', 'file'], ['authority', 'docs'],
        ['mime', mime.includes('text/plain') ? 'text/plain' : mime.join(',')],
        ['bytes', content], ['sha256', Array.from(hash).map((b: number) => b.toString(16).padStart(2, '0')).join('')]
      ]);
    } finally { fs.closeSync(file); }
  }

  private async dispatch(call: MethodCall): Promise<Object | null> {
    switch (call.method) {
      case 'secureWrite': return this.writeAsset(call.argument('value') as string);
      case 'secureRead': return this.readAsset();
      case 'secureClear': return this.clearAsset();
      case 'secureInfo': {
        const query = this.query();
        query.set(asset.Tag.RETURN_TYPE, asset.ReturnType.ATTRIBUTES);
        const row = (await asset.query(query))[0];
        return new Map<string, Object>([
          ['storagePolicy', 'system_asset'], ['syncNever', row.get(asset.Tag.SYNC_TYPE) === asset.SyncType.NEVER],
          ['deviceUnlocked', row.get(asset.Tag.ACCESSIBILITY) === asset.Accessibility.DEVICE_UNLOCKED],
          ['retainedAfterUninstall', row.get(asset.Tag.IS_PERSISTENT) === true],
          ['metadataExcludesSecret', !row.has(asset.Tag.SECRET)], ['hardwareProtection', 'NOT_TESTED']
        ]);
      }
      case 'secureInvalidUpdate': {
        const invalid: asset.AssetMap = new Map();
        invalid.set(asset.Tag.SECRET, new Uint8Array(0));
        await asset.update(this.query(), invalid);
        return false;
      }
      case 'secureAliasIsolation': {
        try { await asset.query(this.query('soloops-m0-absent')); return false; }
        catch (error) {
          if ((error as BusinessError).code === asset.ErrorCode.NOT_FOUND) return true;
          throw error as Error;
        }
      }
      case 'cacheWrite': {
        const value = call.argument('value') as string;
        if (!['dark', 'light', 'restart-dark'].includes(value)) throw new ProbeError('NON_SENSITIVE_ONLY');
        const cache = await preferences.getPreferences(this.context, { name: CACHE });
        await cache.put(this.scope(call), value); await cache.flush(); return true;
      }
      case 'cacheRead': {
        const cache = await preferences.getPreferences(this.context, { name: CACHE });
        return await cache.has(this.scope(call)) ? await cache.get(this.scope(call), '') as string : null;
      }
      case 'cacheClear': {
        const cache = await preferences.getPreferences(this.context, { name: CACHE });
        await cache.clear(); await cache.flush(); return true;
      }
      case 'uriDenied': {
        // Enforce the same one-operation picker grant at our bridge boundary.
        // This is a bridge policy check, not a claim about OS-level URI denial.
        try {
          await this.readSelectedUri('file://docs/storage/Users/currentUser/Documents/soloops-m0-ungranted.txt');
          return false;
        } catch (error) {
          return error instanceof ProbeError && error.code === 'DOCUMENT_NOT_SELECTED';
        }
      }
      case 'prepareFiles': {
        for (const kind of ['small', 'large', 'ungranted']) {
          const uris = await new picker.DocumentViewPicker(this.context).save({ newFileNames: [`soloops-m0-${kind}.txt`] });
          if (uris.length !== 1) throw new ProbeError('SAVE_CANCELLED');
          const file = fs.openSync(uris[0], fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
          try {
            if (kind === 'large') {
              const chunk = new Uint8Array(65536).fill(77);
              for (let i = 0; i < 32; i++) fs.writeSync(file.fd, chunk.buffer);
              fs.writeSync(file.fd, new Uint8Array([77]).buffer);
            } else { fs.writeSync(file.fd, TEXT); }
          } finally { fs.closeSync(file); }
          console.info(`SOLOOPS_M0_FIXTURE ${kind} ${uris[0]}`);
        }
        return true;
      }
      case 'pick': return this.pick();
      case 'share': {
        const bytes = call.argument('bytes') as Uint8Array;
        if (bytes.byteLength > LIMIT) throw new ProbeError('FILE_TOO_LARGE');
        if (new util.TextDecoder().decodeToString(bytes) !== TEXT) throw new ProbeError('SYNTHETIC_ONLY');
        await this.clearShare();
        const path = `${this.context.cacheDir}/soloops-m0-share.txt`;
        const file = fs.openSync(path, fs.OpenMode.CREATE | fs.OpenMode.WRITE_ONLY | fs.OpenMode.TRUNC);
        try { fs.writeSync(file.fd, bytes.buffer); } finally { fs.closeSync(file); }
        const data = new systemShare.SharedData({
          utd: uniformTypeDescriptor.UniformDataType.PLAIN_TEXT,
          uri: fileUri.getUriFromPath(path), title: 'SoloOps M0 synthetic file'
        });
        this.controller = new systemShare.ShareController(data);
        this.controller.on('dismiss', () => { console.info('SOLOOPS_M0_SHARE_DISMISSED'); });
        await this.controller.show(this.context, { selectionMode: systemShare.SelectionMode.SINGLE });
        return 'panel_opened';
      }
      case 'shareClear': return this.clearShare();
      case 'external': {
        await this.context.openLink('https://127.0.0.1:18443/api/health/live');
        return 'browser_opened';
      }
      default: throw new ProbeError('METHOD_UNSUPPORTED');
    }
  }
}