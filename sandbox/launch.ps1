<#
.SYNOPSIS
  Open the contained 5G incident-response lab in Windows Sandbox (run on the HOST).

.DESCRIPTION
  Fills this checkout's absolute paths into sandbox\5g-sandbox.wsb, writes
  sandbox\5g-sandbox.local.wsb (git-ignored) and opens it.  Inside the
  sandbox, sandbox\setup.ps1 runs automatically.

  The repository (including the prebuilt kb\index\) is mapped READ-ONLY; only
  sandbox\work\ is writable.  Nothing in the lab sends traffic anywhere; the
  network is only needed to download Python packages and, optionally, to call
  the Claude API.

.PARAMETER HostPython
  Map the host's Python (with the packages already installed) read-only
  instead of downloading Python and packages inside the sandbox.

.PARAMETER PythonDir
  Host Python folder for -HostPython (default: %LOCALAPPDATA%\Programs\Python\Python312).

.PARAMETER Offline
  Disable networking in the sandbox (implies -HostPython; the agent then uses
  the offline playbook provider).

.PARAMETER SelfTest
  Run one non-interactive scenario inside the sandbox and write
  sandbox\work\selftest.txt, then leave the console open.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File sandbox\launch.ps1
  powershell -ExecutionPolicy Bypass -File sandbox\launch.ps1 -Offline
#>
param(
    [switch]$HostPython,
    [string]$PythonDir = "$env:LOCALAPPDATA\Programs\Python\Python312",
    [switch]$Offline,
    [switch]$SelfTest
)
$ErrorActionPreference = 'Stop'

$sandboxExe = Join-Path $env:WINDIR 'System32\WindowsSandbox.exe'
if (-not (Test-Path $sandboxExe)) {
    throw "Windows Sandbox is not enabled. Turn on the 'Windows Sandbox' Windows feature and reboot."
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$work = Join-Path $PSScriptRoot 'work'
New-Item -ItemType Directory -Force $work | Out-Null

if (-not (Test-Path (Join-Path $repo 'kb\index\manifest.json'))) {
    Write-Warning "kb\index\manifest.json not found - the prebuilt index is missing. The policy panel will show obligations as UNVERIFIED."
}

if ($Offline) { $HostPython = $true }
$pythonMapping = ''
if ($HostPython) {
    if (-not (Test-Path (Join-Path $PythonDir 'python.exe'))) {
        throw "No python.exe in $PythonDir (pass -PythonDir)."
    }
    $pythonMapping = @"
<MappedFolder>
      <HostFolder>$PythonDir</HostFolder>
      <SandboxFolder>C:\lab\python</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
"@
}

$flag = Join-Path $work 'SELFTEST'
if ($SelfTest) { Set-Content -Path $flag -Value 'run' -Encoding ascii }
elseif (Test-Path $flag) { Remove-Item $flag }

$template = Get-Content (Join-Path $PSScriptRoot '5g-sandbox.wsb') -Raw
$config = $template.Replace('__REPO__', $repo).Replace('__WORK__', $work).
    Replace('__NETWORKING__', $(if ($Offline) { 'Disable' } else { 'Enable' })).
    Replace('__PYTHON_MAPPING__', $pythonMapping)
$out = Join-Path $PSScriptRoot '5g-sandbox.local.wsb'
Set-Content -Path $out -Value $config -Encoding utf8

Write-Host "Repository (read-only): $repo"
Write-Host "Work folder (writable): $work"
Write-Host "Python: $(if ($HostPython) { "$PythonDir (read-only)" } else { 'downloaded inside the sandbox' })"
Write-Host "Networking: $(if ($Offline) { 'disabled' } else { 'enabled' })"
Write-Host "Opening $out"
Start-Process $out
