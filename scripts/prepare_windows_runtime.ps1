# Static extraction of a SHA256-pinned official archive. Never executes installer.
param([Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
$Repo=Split-Path $PSScriptRoot -Parent
$Pin=Get-Content -LiteralPath (Join-Path $Repo 'ci/workbuddy-windows-pin.json') -Raw | ConvertFrom-Json
if (Test-Path -LiteralPath $Output) { throw 'Runtime output must be a new directory.' }
$SevenZip=(Get-Command 7z -ErrorAction SilentlyContinue).Source
if (-not $SevenZip) { $SevenZip=Join-Path $env:ProgramFiles '7-Zip/7z.exe' }
if (-not (Test-Path -LiteralPath $SevenZip)) { throw 'Trusted preinstalled 7-Zip required; no automatic dependency installation.' }
New-Item -ItemType Directory -Path $Output | Out-Null
$Installer=Join-Path $Output 'WorkBuddy-pinned.exe'
Invoke-WebRequest -Uri $Pin.url -OutFile $Installer
$Actual=(Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant()
if ($Actual -ne $Pin.sha256) { throw 'Official artifact hash mismatch; stop without executing or extracting it.' }
$Outer=Join-Path $Output 'outer';$Payload=Join-Path $Output 'payload';$NodeDir=Join-Path $Output 'node'
& $SevenZip x '-y' "-o$Outer" $Installer | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'NSIS static extraction failed' }
$Inner=Join-Path $Outer '$PLUGINSDIR/app-64.7z'
if (-not (Test-Path -LiteralPath $Inner)) { throw 'Pinned NSIS layout changed' }
& $SevenZip x '-y' "-o$Payload" $Inner | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Application payload extraction failed' }
$NodeZip=Join-Path $Payload 'resources/vendor/node.zip'
if (-not (Test-Path -LiteralPath $NodeZip)) { throw 'Pinned bundled Node archive absent' }
& $SevenZip x '-y' "-o$NodeDir" $NodeZip | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Bundled Node extraction failed' }
$Node=Join-Path $NodeDir 'node-v22.22.2-win-x64/node.exe'
$Cli=Join-Path $Payload 'resources/app.asar.unpacked/cli/bin/codebuddy'
if (-not (Test-Path -LiteralPath $Node) -or -not (Test-Path -LiteralPath $Cli)) { throw 'Pinned runtime paths unavailable' }
$CliPackage=Get-Content -LiteralPath (Join-Path $Payload 'resources/app.asar.unpacked/cli/package.json') -Raw | ConvertFrom-Json
if ($CliPackage.version -ne $Pin.cli_version) { throw 'Bundled CLI package version mismatch' }
$NodeVersion=& $Node --version
if ($LASTEXITCODE -ne 0 -or $NodeVersion.Trim() -ne 'v22.22.2') { throw 'Bundled Node version mismatch' }
$Report=@{node=$Node;cli=$Cli;version=$Pin.version;sha256=$Actual;installer_executed=$false}
$Report | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Output 'runtime.json') -Encoding utf8
if ($env:GITHUB_ENV) {
 "WORKBUDDY_TEST_NODE=$Node" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
 "WORKBUDDY_TEST_CLI=$Cli" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
}
$Report | ConvertTo-Json
