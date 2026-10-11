import { FlutterAbility, FlutterEngine, MethodChannel } from '@ohos/flutter_ohos';
import { GeneratedPluginRegistrant } from '../plugins/GeneratedPluginRegistrant';
import { M0Bridge } from './M0Bridge';
import { DeviceBridge } from './DeviceBridge';

export default class EntryAbility extends FlutterAbility {
  configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)
    GeneratedPluginRegistrant.registerWith(flutterEngine)
    new MethodChannel(flutterEngine.getDartExecutor().getBinaryMessenger(), 'soloops/m0')
      .setMethodCallHandler(new M0Bridge(this.context));
    new MethodChannel(flutterEngine.getDartExecutor().getBinaryMessenger(), 'soloops/device')
      .setMethodCallHandler(new DeviceBridge(this.context));
  }
}