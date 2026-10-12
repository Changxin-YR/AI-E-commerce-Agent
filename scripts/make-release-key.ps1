# Creates the local release keystore and the ignored Gradle signing properties.
# Secrets stay in .local/android/keystore; only this script is versioned.
param(
    [string]$Keytool = 'D:/Javajdk/bin/keytool.exe'
)
$ErrorActionPreference = 'Stop'
$repo = Split-Path $PSScriptRoot -Parent
$dir = Join-Path $repo '.local/android/keystore'
$store = Join-Path $dir 'soloops-release.jks'
$credentials = Join-Path $dir 'credentials.txt'
$properties = Join-Path $repo 'frontend/android/keystore.properties'
New-Item -ItemType Directory -Force -Path $dir | Out-Null

if (!(Test-Path $store)) {
    if (!(Test-Path $Keytool)) { throw "keytool not found: $Keytool" }
    $bytes = New-Object byte[] 24
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $password = [Convert]::ToBase64String($bytes).Replace('+', 'A').Replace('/', 'B').Replace('=', '')
    # keytool writes progress to stderr; keep PowerShell from treating it as a failure.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & $Keytool -genkeypair -v -keystore $store -storetype PKCS12 -alias soloops-release `
        -keyalg RSA -keysize 4096 -validity 3650 -storepass $password -keypass $password `
        -dname 'CN=SoloOps Android Release, OU=Local Build, O=SoloOps, L=Local, ST=Local, C=CN' 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    if ($code -ne 0) { throw "keytool failed ($code): $output" }
    "store=$store`nalias=soloops-release`npassword=$password" | Set-Content -Path $credentials -Encoding UTF8
    Write-Output "created keystore $store"
} else {
    Write-Output "keystore already exists: $store"
}

$password = (Get-Content $credentials | Where-Object { $_ -like 'password=*' }) -replace '^password=', ''
if (!$password) { throw "no password recorded in $credentials" }
# Write without a BOM: Java's Properties loader would fold a BOM into the first key.
$propertiesText = @"
storeFile=$($store -replace '\\', '/')
storePassword=$password
keyAlias=soloops-release
keyPassword=$password
"@
[System.IO.File]::WriteAllText($properties, $propertiesText, (New-Object System.Text.UTF8Encoding($false)))
Write-Output "wrote $properties (ignored by git)"
