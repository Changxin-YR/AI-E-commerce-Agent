param(
    [string]$FlutterSdk,
    [string]$DevEcoRoot = 'C:/Program Files/Huawei/DevEco Studio'
)
$ErrorActionPreference = 'Stop'
$repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
if (-not $FlutterSdk) { $FlutterSdk = Join-Path $repositoryRoot '.local/toolchains/flutter-oh-api22' }
$sdkRoot = (Resolve-Path -LiteralPath $FlutterSdk).Path
$lock = Get-Content -LiteralPath (Join-Path $repositoryRoot 'apps/soloops_flutter/toolchain.lock.json') -Raw | ConvertFrom-Json
$sdkCommit = (& git -C $sdkRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sdkCommit -ne $lock.commit) { throw 'Flutter SDK commit does not match toolchain.lock.json.' }
$env:DEVECO_SDK_HOME = Join-Path $DevEcoRoot 'sdk'
$env:FLUTTER_ROOT = $sdkRoot
$env:Path = "$sdkRoot/bin;$(Join-Path $DevEcoRoot 'tools/node');$(Join-Path $DevEcoRoot 'tools/ohpm/bin');$(Join-Path $DevEcoRoot 'tools/hvigor/bin');" + $env:Path
$defines = Get-Content -LiteralPath (Join-Path $repositoryRoot '.local/mobile-m0b/tls/dart-defines.json') -Raw | ConvertFrom-Json
$encoded = ($defines.PSObject.Properties | ForEach-Object {
    [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($_.Name + '=' + $_.Value))
}) -join ','
$packageConfig = Join-Path $repositoryRoot 'apps/soloops_flutter/.dart_tool/package_config.json'
Push-Location (Join-Path $repositoryRoot 'apps/soloops_flutter/ohos')
try {
    & hvigorw.bat assembleHap -p product=default -p buildMode=debug --no-daemon -p FLUTTER_TARGET=lib/main.dart -p TARGET_PLATFORM=ohos-x64 -p DART_OBFUSCATION=false -p TRACK_WIDGET_CREATION=true -p TREE_SHAKE_ICONS=false -p "DART_DEFINES=$encoded" -p "PACKAGE_CONFIG=$packageConfig"
    exit $LASTEXITCODE
} finally { Pop-Location }