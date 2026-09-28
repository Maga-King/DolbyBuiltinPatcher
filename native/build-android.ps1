param(
    [string]$Ndk = "$env:LOCALAPPDATA\Android\Sdk\ndk\28.2.13676358"
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$llvm = Join-Path $Ndk 'toolchains\llvm\prebuilt\windows-x86_64\bin'
$clang = Join-Path $llvm 'clang.exe'
if (!(Test-Path -LiteralPath $clang)) { throw "NDK clang missing: $clang" }
$output = Join-Path $projectRoot 'android\app\src\main\jniLibs\arm64-v8a'
$tempDir = Join-Path $projectRoot 'build\android-secilc'
New-Item -ItemType Directory -Force -Path $output,$tempDir | Out-Null
$sourceRoot = Join-Path $projectRoot 'third_party\selinux'
$lexer = Join-Path $tempDir 'cil_lexer.c'
# flex is a build-time tool only. No host compiler/WSL is needed on the phone.
$linuxLexer = (& wsl --exec wslpath -a -u $lexer.Replace('\','/')).Trim()
$linuxGrammar = (& wsl --exec wslpath -a -u (Join-Path $sourceRoot 'libsepol\cil\src\cil_lexer.l').Replace('\','/')).Trim()
& wsl --exec flex -o $linuxLexer $linuxGrammar
if ($LASTEXITCODE) { throw 'flex failed' }
$sources = @((Get-ChildItem -LiteralPath (Join-Path $sourceRoot 'libsepol\src') -Filter '*.c').FullName)
$sources += (Get-ChildItem -LiteralPath (Join-Path $sourceRoot 'libsepol\cil\src') -Filter '*.c' | Where-Object Name -ne 'cil_lexer.c').FullName
$sources += $lexer,(Join-Path $sourceRoot 'secilc\secilc.c')
$compileArgs = @('--target=aarch64-linux-android26','-O2','-fPIE','-pie','-D_GNU_SOURCE','-DANDROID',
    '-Werror=implicit-function-declaration','-Wl,-z,max-page-size=16384',
    ('-I'+(Join-Path $sourceRoot 'libsepol\include')),('-I'+(Join-Path $sourceRoot 'libsepol\cil\include')),
    ('-I'+(Join-Path $sourceRoot 'libsepol\src')),('-I'+(Join-Path $sourceRoot 'libsepol\cil\src')))
& $clang @compileArgs @sources -o (Join-Path $output 'libsecilc.so')
if ($LASTEXITCODE) { throw 'Android secilc build failed' }
& (Join-Path $llvm 'llvm-strip.exe') (Join-Path $output 'libsecilc.so')
if ($LASTEXITCODE) { throw 'strip failed' }
Write-Output "Built Android ARM64 PIE: $output\libsecilc.so"
