# No execution-policy changes or downloads. Invoke from a trusted PowerShell session.
param(
  [Parameter(Mandatory=$true)][ValidateSet('install','uninstall','check')][string]$Action,
  [Parameter(Mandatory=$true)][string]$Project,
  [string]$Cli,
  [string]$Node,
  [string]$Python,
  [ValidateSet('powershell','posix')][string]$HookShell='powershell'
)
$ErrorActionPreference='Stop'
$candidates=@()
if ($Python) { $candidates+=,@($Python) }
else {
  if (Get-Command py -ErrorAction SilentlyContinue) { $candidates+=,@('py','-3') }
  if (Get-Command python -ErrorAction SilentlyContinue) { $candidates+=,@('python') }
}
$chosen=$null
foreach ($candidate in $candidates) {
  $exe=$candidate[0];$prefix=@($candidate | Select-Object -Skip 1)
  & $exe @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)'
  if ($LASTEXITCODE -eq 0) { $chosen=$candidate;break }
}
if (-not $chosen) { throw 'Python 3.10+ not found. Provide -Python path to a trusted compatible python.exe. Nothing installed.' }
$exe=$chosen[0];$prefix=@($chosen | Select-Object -Skip 1)
$params=@('-X','utf8',(Join-Path $PSScriptRoot 'manage.py'),$Action,'--project',$Project,'--hook-shell',$HookShell)
if ($Cli) { $params+=@('--cli',$Cli) }
if ($Node) { $params+=@('--node',$Node) }
& $exe @prefix @params
if ($LASTEXITCODE -ne 0) { throw "Native project hook $Action failed; inspect the preceding diagnostic." }
