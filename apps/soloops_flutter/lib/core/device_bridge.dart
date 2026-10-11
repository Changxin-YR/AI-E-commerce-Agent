import 'dart:typed_data';
import 'package:flutter/services.dart';

class DeviceBridge {
  static const channel = MethodChannel('soloops/device');
  Future<String?> readSession() => channel.invokeMethod<String>('sessionRead');
  Future<void> writeSession(String value) =>
      channel.invokeMethod<void>('sessionWrite', {'value': value});
  Future<void> clearSession() => channel.invokeMethod<void>('sessionClear');
  Future<Map<String, dynamic>> settings() async => Map<String, dynamic>.from(
      await channel.invokeMapMethod<String, dynamic>('settingsRead') ?? {});
  Future<void> saveSettings(String baseUrl, int? shopId) =>
      channel.invokeMethod<void>(
          'settingsWrite', {'baseUrl': baseUrl, 'shopId': shopId ?? 0});
  Future<Map<String, dynamic>?> pickFile() async {
    final result = await channel.invokeMapMethod<String, dynamic>('pickFile');
    return result == null ? null : Map<String, dynamic>.from(result);
  }

  Future<bool> saveFile(String name, Uint8List bytes) async =>
      await channel
          .invokeMethod<bool>('saveFile', {'name': name, 'bytes': bytes}) ??
      false;
  Future<void> shareFile(String name, Uint8List bytes) =>
      channel.invokeMethod<void>('shareFile', {'name': name, 'bytes': bytes});
}
