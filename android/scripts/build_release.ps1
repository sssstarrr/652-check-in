$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sdkRoot = if (-not [string]::IsNullOrWhiteSpace($env:ANDROID_SDK_ROOT)) {
    $env:ANDROID_SDK_ROOT
} elseif (-not [string]::IsNullOrWhiteSpace($env:ANDROID_HOME)) {
    $env:ANDROID_HOME
} else {
    "D:\Sdk"
}
$javaHome = if (-not [string]::IsNullOrWhiteSpace($env:JAVA_HOME)) {
    $env:JAVA_HOME
} else {
    "D:\Program Files\Android\Android Studio\jbr"
}
$signingRoot = Join-Path $env:LOCALAPPDATA "Checkin652Android\signing"
$keystore = Join-Path $signingRoot "checkin-652-release.jks"
$passwordFile = Join-Path $signingRoot "password.dpapi"
$keyAlias = "checkin652"

if (-not (Test-Path -LiteralPath (Join-Path $sdkRoot "build-tools\37.0.0\apksigner.bat"))) {
    throw "Android SDK not found at $sdkRoot; set ANDROID_SDK_ROOT or ANDROID_HOME"
}
if (-not (Test-Path -LiteralPath (Join-Path $javaHome "bin\keytool.exe"))) {
    throw "Java runtime not found at $javaHome; set JAVA_HOME"
}

New-Item -ItemType Directory -Force -Path $signingRoot | Out-Null

if (-not (Test-Path -LiteralPath $passwordFile)) {
    $random = New-Object byte[] 32
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($random)
    } finally {
        $generator.Dispose()
    }
    $plainPassword = ([BitConverter]::ToString($random)).Replace("-", "")
    $securePassword = ConvertTo-SecureString $plainPassword -AsPlainText -Force
    $securePassword | ConvertFrom-SecureString | Set-Content -Encoding UTF8 -LiteralPath $passwordFile
}

$encryptedPassword = (Get-Content -Raw -Encoding UTF8 -LiteralPath $passwordFile).Trim()
$storedPassword = $encryptedPassword | ConvertTo-SecureString
$credential = New-Object System.Management.Automation.PSCredential("checkin652", $storedPassword)
$plainPassword = $credential.GetNetworkCredential().Password

if (-not (Test-Path -LiteralPath $keystore)) {
    & (Join-Path $javaHome "bin\keytool.exe") `
        -genkeypair `
        -keystore $keystore `
        -alias $keyAlias `
        -keyalg RSA `
        -keysize 3072 `
        -validity 10000 `
        -dname "CN=652 Checkin Android, O=Local Release" `
        -storepass $plainPassword `
        -keypass $plainPassword `
        -noprompt
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create release keystore"
    }
}

$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:JAVA_HOME = $javaHome
$env:CHECKIN_KEYSTORE_PATH = $keystore
$env:CHECKIN_KEYSTORE_PASSWORD = $plainPassword
$env:CHECKIN_KEY_ALIAS = $keyAlias
$env:CHECKIN_KEY_PASSWORD = $plainPassword

$drive = "X:"
if (subst.exe | Select-String -SimpleMatch "$drive\:") {
    throw "$drive is already in use; remove that mapping and retry"
}

try {
    subst.exe $drive $projectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to map the project to $drive"
    }
    Set-Location "$drive\"
    .\gradlew.bat clean testDebugUnitTest lintRelease assembleRelease
    if ($LASTEXITCODE -ne 0) {
        throw "Android release build failed"
    }
} finally {
    Set-Location $projectRoot
    subst.exe $drive /D | Out-Null
    Remove-Item Env:CHECKIN_KEYSTORE_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:CHECKIN_KEY_PASSWORD -ErrorAction SilentlyContinue
    $plainPassword = $null
}

$sourceApk = Join-Path $projectRoot "app\build\outputs\apk\release\app-release.apk"
$distDirectory = Join-Path $projectRoot "dist"
$distApk = Join-Path $distDirectory "652-Checkin-Android-v1.0.0.apk"
New-Item -ItemType Directory -Force -Path $distDirectory | Out-Null
Copy-Item -Force -LiteralPath $sourceApk -Destination $distApk

& (Join-Path $sdkRoot "build-tools\37.0.0\apksigner.bat") verify --verbose --print-certs $distApk
if ($LASTEXITCODE -ne 0) {
    throw "Release APK signature verification failed"
}
Get-Item -LiteralPath $distApk | Select-Object FullName, Length, LastWriteTime
Get-FileHash -Algorithm SHA256 -LiteralPath $distApk
