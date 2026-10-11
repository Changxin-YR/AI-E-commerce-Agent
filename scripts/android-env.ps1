param(
    [string]$JavaHome = 'D:/Javajdk',
    [string]$SdkRoot = ''
)
$ErrorActionPreference = 'Stop'
$AndroidRepo = Split-Path $PSScriptRoot -Parent
if (!$SdkRoot) { $SdkRoot = "$AndroidRepo/.local/android/sdk" }
if (!(Test-Path "$JavaHome/bin/java.exe") -or !(Test-Path "$SdkRoot/platforms/android-36")) {
    throw 'Supply Java 21 and an Android SDK containing platform 36.'
}
$env:JAVA_HOME = $JavaHome
$env:ANDROID_HOME = $SdkRoot
$env:ANDROID_SDK_ROOT = $SdkRoot
$env:ANDROID_AVD_HOME = "$AndroidRepo/.local/android/avd"
$env:GRADLE_USER_HOME = "$AndroidRepo/.local/android/gradle"
$env:PATH = "$JavaHome/bin;$AndroidRepo/.local/android/sdk/platform-tools;$env:PATH"
$env:VITE_SOLOOPS_API_ORIGIN = 'http://10.0.2.2:8011'

