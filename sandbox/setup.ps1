<#
  Runs INSIDE Windows Sandbox (started by the LogonCommand in 5g-sandbox.wsb).

  1. Points the lab at the read-only repository and the writable work folder.
  2. Uses the host's Python if it was mapped (launch.ps1 -HostPython), else
     downloads Python 3.12 from python.org and installs the requirements.
  3. Copies the embedding model cache to a writable place and checks the
     prebuilt index against its manifest hashes (it is never rebuilt here).
  4. Offers the attack menu and runs `python run.py --attack <id>`.

  The sandbox is ephemeral: closing it discards everything except C:\lab\work.
#>
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Repo = 'C:\lab\repo'
$Work = 'C:\lab\work'
Start-Transcript -Path (Join-Path $Work 'setup.log') -Force | Out-Null
Write-Host "=== Contained 5G incident-response lab (Windows Sandbox) ===" -ForegroundColor Cyan

# --- environment -------------------------------------------------------------
$env:LAB_WORK_DIR = $Work                          # sim state, logs, reports (writable)
$env:KB_INDEX_DIR = Join-Path $Repo 'kb\index'     # prebuilt index (read-only mount)
$env:PYTHONDONTWRITEBYTECODE = '1'                 # repository is read-only
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [Text.Encoding]::UTF8     # show the panels' check marks correctly
$OutputEncoding = [Text.Encoding]::UTF8
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = '1'

# --- Python ------------------------------------------------------------------
if (Test-Path 'C:\lab\python\python.exe') {
    $Python = 'C:\lab\python\python.exe'
    Write-Host "Using the host's Python (mapped read-only): $Python"
} else {
    $Python = 'C:\lab\py\python.exe'
    if (-not (Test-Path $Python)) {
        $version = '3.12.10'
        $installer = Join-Path $env:TEMP "python-$version-amd64.exe"
        Write-Host "Downloading Python $version from python.org ..."
        Invoke-WebRequest "https://www.python.org/ftp/python/$version/python-$version-amd64.exe" -OutFile $installer
        Write-Host "Installing Python to C:\lab\py ..."
        Start-Process $installer -Wait -ArgumentList '/quiet', 'InstallAllUsers=0', 'TargetDir=C:\lab\py',
            'Include_test=0', 'Include_launcher=0', 'PrependPath=0', 'Shortcuts=0'
    }
    Write-Host "Installing requirements (CPU-only) ..."
    & $Python -m pip install --disable-pip-version-check -q -r (Join-Path $Repo 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
}

# --- embedding model: copy the host's cache so loading needs no download ------
$hostCache = Join-Path $Repo 'knowledge_base\.model_cache'
if (Test-Path $hostCache) {
    Copy-Item $hostCache 'C:\lab\model_cache' -Recurse -Force
    $env:KB_MODEL_CACHE = 'C:\lab\model_cache'
    $env:HF_HUB_OFFLINE = '1'
    Write-Host "Embedding model: copied from the host cache (no download)."
} else {
    $env:KB_MODEL_CACHE = 'C:\lab\model_cache'
    Write-Host "Embedding model: not cached on the host; it will be downloaded on first search (needs network)."
}

# --- API key: from the environment or the host's .env (never committed) --------
Set-Location $Repo
if (-not $env:ANTHROPIC_API_KEY -and -not (Test-Path (Join-Path $Repo '.env'))) {
    Write-Host "No ANTHROPIC_API_KEY: the agent will use the offline playbook provider." -ForegroundColor Yellow
    Write-Host "(To use Claude: put ANTHROPIC_API_KEY=... in .env on the host, or set it in this window.)"
}

# --- index check ---------------------------------------------------------------
& $Python -c "import kb.retriever as r; p = r.verify(); print('Index:', len(r.categories()), 'categories,', 'hashes match the manifest' if not p else p)"
if ($LASTEXITCODE -ne 0) { Write-Warning "Index not available - obligations will be shown UNVERIFIED." }

# --- self-test (launch.ps1 -SelfTest) --------------------------------------------
if (Test-Path (Join-Path $Work 'SELFTEST')) {
    Remove-Item (Join-Path $Work 'SELFTEST')
    Write-Host "Self-test: signalling_storm_amf, offline provider, auto-approve ..."
    & $Python run.py --attack signalling_storm_amf --provider offline --auto *>&1 |
        Out-File -FilePath (Join-Path $Work 'selftest.txt') -Encoding utf8
    Write-Host "Self-test exit code $LASTEXITCODE -> C:\lab\work\selftest.txt"
}

# --- menu ------------------------------------------------------------------------
Stop-Transcript | Out-Null
while ($true) {
    Write-Host ""
    & $Python run.py --list
    Write-Host ""
    $attack = Read-Host "Attack number (1-13) or id to run ('ui' = web UI, 'q' = quit)"
    if ($attack -eq 'q') { break }
    if ($attack -eq 'ui') {
        Write-Host "Starting the web UI on http://localhost:8501 (Ctrl+C to stop)"
        & $Python -m streamlit run ir\ui.py --server.headless true --browser.gatherUsageStats false
        continue
    }
    if ($attack) { & $Python run.py --attack $attack }
}
