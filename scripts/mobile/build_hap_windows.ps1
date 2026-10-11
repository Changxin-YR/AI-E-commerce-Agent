#Requires -Version 7.0
param(
    [string]$FlutterSdk = $env:SOLOOPS_FLUTTER_SDK,
    [string]$BuildRoot = (Join-Path $env:TEMP ('soloops-hap-' + [guid]::NewGuid().ToString('N').Substring(0, 8))),
    [switch]$Unsigned
)

$ErrorActionPreference = 'Stop'
$repositoryRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $FlutterSdk) { throw 'Set SOLOOPS_FLUTTER_SDK or pass -FlutterSdk.' }
$sdkRoot = (Resolve-Path -LiteralPath $FlutterSdk).Path
if ($sdkRoot -match '\s') { throw 'Flutter SDK must have a physical path without whitespace.' }
$buildDirectory = [IO.Path]::GetFullPath($BuildRoot)
if ($buildDirectory -match '\s' -or (Test-Path -LiteralPath $buildDirectory)) {
    throw 'BuildRoot must be a new directory without whitespace.'
}
$flutter = Join-Path $sdkRoot 'bin/flutter.bat'
if (-not (Test-Path -LiteralPath $flutter)) { throw 'Flutter SDK launcher is missing.' }
$lock = Get-Content -LiteralPath (Join-Path $repositoryRoot 'apps/soloops_flutter/toolchain.lock.json') -Raw | ConvertFrom-Json
$sdkCommit = & git -C $sdkRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0 -or $sdkCommit -ne $lock.commit) { throw 'Flutter SDK commit does not match the lock file.' }
$sdkChanges = & git -C $sdkRoot status --porcelain
if ($LASTEXITCODE -ne 0 -or $sdkChanges) { throw 'Flutter SDK checkout must be clean.' }

# Build a byte-identical snapshot of tracked client sources; keep the repository as source of truth.
New-Item -ItemType Directory -Path $buildDirectory | Out-Null
$tracked = & git -C $repositoryRoot ls-files -- apps/soloops_flutter
if ($LASTEXITCODE -ne 0 -or -not $tracked) { throw 'Cannot enumerate tracked Flutter sources.' }
$manifest = @()
foreach ($relative in $tracked) {
    $source = Join-Path $repositoryRoot $relative
    $destination = Join-Path $buildDirectory $relative.Substring('apps/soloops_flutter/'.Length)
    New-Item -ItemType Directory -Path (Split-Path $destination -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination
    $digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $digest) {
        throw "Snapshot mismatch: $relative"
    }
    $manifest += @{ path = $relative; sha256 = $digest }
}
$evidenceDirectory = Join-Path $repositoryRoot '.local/mobile-m0a'
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
$manifest | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $evidenceDirectory 'hap-source-manifest.json') -Encoding UTF8
Write-Output "Snapshot: $buildDirectory; verified $($manifest.Count) source files"

Push-Location $buildDirectory
try {
    & $flutter pub get
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ((Get-FileHash -LiteralPath 'pubspec.lock').Hash -ne (Get-FileHash -LiteralPath (Join-Path $repositoryRoot 'apps/soloops_flutter/pubspec.lock')).Hash) {
        throw 'pub get changed the locked dependencies.'
    }
    & $flutter build hap --debug --no-pub
    $flutterExitCode = $LASTEXITCODE
    Write-Output "Flutter build hap exit code: $flutterExitCode"
    $buildExitCode = $flutterExitCode
    if ($Unsigned) {
        # The locked Flutter wrapper requires signing after Hvigor has built the HAP.
        # Verify the unsigned target with the same native build command and a separate exit code.
        $hvigor = (Get-Command hvigorw.bat -ErrorAction Stop).Source
        $packageConfig = Join-Path $buildDirectory '.dart_tool/package_config.json'
        Push-Location ohos
        try {
            & $hvigor assembleHap -p product=default -p buildMode=debug --no-daemon -p FLUTTER_TARGET=lib/main.dart -p TARGET_PLATFORM=ohos-arm64 -p DART_OBFUSCATION=false -p TRACK_WIDGET_CREATION=true -p TREE_SHAKE_ICONS=false -p "PACKAGE_CONFIG=$packageConfig"
            $buildExitCode = $LASTEXITCODE
        } finally { Pop-Location }
        Write-Output "Hvigor unsigned build exit code: $buildExitCode"
    }
    @{
        flutter_exit_code = $flutterExitCode
        native_build_exit_code = $buildExitCode
        unsigned_requested = [bool]$Unsigned
        sdk_commit = $sdkCommit
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceDirectory 'hap-build-results.json') -Encoding UTF8
    if ($buildExitCode -ne 0) { exit $buildExitCode }
    $suffix = if ($Unsigned) { '*-unsigned.hap' } else { '*-signed.hap' }
    $outputs = @(Get-ChildItem -Path (Join-Path 'ohos/entry/build/default/outputs/default' $suffix) -File)
    if ($outputs.Count -eq 0) { throw 'Build returned success without a HAP artifact.' }
    $artifactDirectory = Join-Path $repositoryRoot 'apps/soloops_flutter/build/ohos/hap'
    New-Item -ItemType Directory -Path $artifactDirectory -Force | Out-Null
    foreach ($artifact in $outputs) {
        Copy-Item -LiteralPath $artifact.FullName -Destination $artifactDirectory
        Get-FileHash -LiteralPath (Join-Path $artifactDirectory $artifact.Name) -Algorithm SHA256
    }
} finally {
    Pop-Location
}
