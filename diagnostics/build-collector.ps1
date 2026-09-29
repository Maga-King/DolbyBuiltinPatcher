$ErrorActionPreference='Stop'
$repo=Split-Path $PSScriptRoot -Parent
$work=Join-Path $repo 'build\diagnostic-helper'
$classes=Join-Path $work 'classes'
$dex=Join-Path $work 'dex'
New-Item -ItemType Directory -Path $classes,$dex -Force | Out-Null
$env:JAVA_HOME='E:\MIO\ace3\tools\temurin17'
$sdk=Join-Path $env:LOCALAPPDATA 'Android\Sdk'
& "$env:JAVA_HOME\bin\javac.exe" --release 8 -encoding UTF-8 -d $classes (Join-Path $PSScriptRoot 'DolbyZip.java')
if ($LASTEXITCODE) {throw 'javac failed'}
& "$sdk\build-tools\35.0.0\d8.bat" --min-api 26 --lib "$sdk\platforms\android-35\android.jar" --output $dex (Join-Path $classes 'DolbyZip.class')
if ($LASTEXITCODE) {throw 'd8 failed'}
$template=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'collect-dolby.sh.in'))
$payload=[Convert]::ToBase64String([IO.File]::ReadAllBytes((Join-Path $dex 'classes.dex')))
$payload=([regex]::Matches($payload,'.{1,76}') | ForEach-Object {$_.Value}) -join "`n"
$result=$template.Replace('@@DEX_BASE64@@',$payload).Replace("`r`n","`n")
$output=Join-Path $work 'dolby-diagnostic.sh'
[IO.File]::WriteAllText($output,$result,(New-Object Text.UTF8Encoding($false)))
Write-Output $output
$databaseOutput=Join-Path $work 'dolby-database-diagnostic.sh'
[IO.File]::WriteAllText($databaseOutput,$result.Replace('DB_ONLY=0','DB_ONLY=1'),(New-Object Text.UTF8Encoding($false)))
Write-Output $databaseOutput
