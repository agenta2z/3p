#Requires -Version 5.1
<#
.SYNOPSIS
    Windows equivalent of run.sh -- start FastAPI server + React UI for OpenStartup.

.DESCRIPTION
    Mirrors the bash run.sh CLI on Windows (PowerShell 5.1+ / 7+).
    Default behavior: start both the backend server (port 8000) and the React UI (port 3000).
    Press Ctrl+C to stop everything.

.PARAMETER Server
    Start only the backend server.

.PARAMETER UI
    Start only the React UI.

.PARAMETER Build
    Build the React UI for production instead of running the dev server.

.PARAMETER Port
    Backend port. Default 8000.

.PARAMETER BindHost
    Backend host. Default 127.0.0.1. (Renamed from --host because $Host is a PowerShell builtin.)

.PARAMETER Reload
    Enable backend auto-reload.

.PARAMETER DebugMode
    Enable backend debug logging. (Renamed from --debug because $Debug is a PowerShell preference variable.)

.PARAMETER RealSessions
    Persistent sessions from a dir. Pass "auto" for default <project>/_runtime, or any path.

.PARAMETER ResumeLatestServer
    Resume the most recently created server.

.PARAMETER ResumeServer
    Resume a specific server dir by name (e.g., server_20260406_...).

.PARAMETER NewServer
    Force a new server (same as default; kept for compatibility with run.sh).

.PARAMETER LlmBackend
    Default conversation backend: mock | rovodev | claude_cli.
    Per-session UI selector overrides this for new sessions.

.PARAMETER LlmModel
    Default model name for the backend factory (e.g. "sonnet" for claude_cli).
    Backend-specific; ignored by backends that don't accept a model_name.

.EXAMPLE
    .\run.ps1
    Start both server (8000) and UI (3000).

.EXAMPLE
    .\run.ps1 -Server -Port 9000 -DebugMode
    Start only the backend on port 9000 with debug logging.

.EXAMPLE
    .\run.ps1 -UI
    Start only the React dev server.

.EXAMPLE
    $env:OPENSTARTUP_PYTHON = "C:\Users\me\miniforge3\python.exe"; .\run.ps1
    Override the Python interpreter.
#>
[CmdletBinding()]
param(
    [switch]$Server,
    [switch]$UI,
    [switch]$Build,
    [int]$Port = 8000,
    [string]$BindHost = "127.0.0.1",
    [switch]$Reload,
    [switch]$DebugMode,
    [string]$RealSessions,
    [switch]$ResumeLatestServer,
    [string]$ResumeServer,
    [switch]$NewServer,
    [string]$LlmBackend,
    [string]$LlmModel
)

$ErrorActionPreference = "Stop"

# ── Resolve script directory + sibling paths ─────────────────────────
$SCRIPT_DIR    = Split-Path -Parent $MyInvocation.MyCommand.Path
$SERVER_DIR    = Join-Path $SCRIPT_DIR "server"
$UI_DIR        = Join-Path $SCRIPT_DIR "ui"
$PROJECT_ROOT  = (Resolve-Path (Join-Path $SCRIPT_DIR "..\..")).Path  # OpenStartup/
$CORE_PROJECTS = (Resolve-Path (Join-Path $PROJECT_ROOT "..")).Path   # CoreProjects/

# ── PYTHONPATH (Windows uses ';' as separator) ───────────────────────
# Strictly optional -- run_server.py has its own sys.path fallback -- but matches
# the bash script's behavior so external entry points see the same env.
$extraPaths = @()
foreach ($lib in @(
    (Join-Path $CORE_PROJECTS "AgentFoundation\src"),
    (Join-Path $CORE_PROJECTS "RichPythonUtils\src"),
    (Join-Path $PROJECT_ROOT "src")
)) {
    if (Test-Path -LiteralPath $lib -PathType Container) { $extraPaths += $lib }
}
if ($extraPaths.Count -gt 0) {
    $newPath = ($extraPaths -join ";")
    if ($env:PYTHONPATH) { $env:PYTHONPATH = "$newPath;$($env:PYTHONPATH)" }
    else { $env:PYTHONPATH = $newPath }
}

# ── Defaults ─────────────────────────────────────────────────────────
$PYTHON = if ($env:OPENSTARTUP_PYTHON) { $env:OPENSTARTUP_PYTHON } else { "python" }

# ── Decide what to run ───────────────────────────────────────────────
# bash run.sh logic: --server -> only server; --ui -> only ui; neither -> both;
#                    both flags -> both (same as default).
$runServer = -not $UI -or $Server
$runUI     = -not $Server -or $UI

# ── Build server CLI args ────────────────────────────────────────────
$serverArgs = @("--host", $BindHost, "--port", "$Port")
if ($Reload)    { $serverArgs += "--reload" }
if ($DebugMode) { $serverArgs += "--debug" }
if ($PSBoundParameters.ContainsKey('RealSessions')) {
    $dir = if ([string]::IsNullOrWhiteSpace($RealSessions) -or $RealSessions -eq "auto") {
        Join-Path $PROJECT_ROOT "_runtime"
    } else {
        $RealSessions
    }
    $serverArgs += @("--real-sessions", $dir)
    $script:RealSessionsResolved = $dir
}
if ($ResumeServer)        { $serverArgs += @("--resume-server", $ResumeServer) }
if ($ResumeLatestServer)  { $serverArgs += "--resume-latest-server" }
if ($NewServer)           { $serverArgs += @("--resume-server", "new") }
if ($LlmBackend)          { $serverArgs += @("--llm-backend", $LlmBackend) }
if ($LlmModel)            { $serverArgs += @("--llm-model", $LlmModel) }

# ── Logging helpers ──────────────────────────────────────────────────
function Write-RunLog  { param($m) Write-Host "[run.ps1] $m" -ForegroundColor Cyan }
function Write-RunOk   { param($m) Write-Host "[run.ps1] $m" -ForegroundColor Green }
function Write-RunWarn { param($m) Write-Host "[run.ps1] $m" -ForegroundColor Yellow }
function Write-RunErr  { param($m) Write-Host "[run.ps1] $m" -ForegroundColor Red }

# ── Process tracking + tree-kill cleanup ─────────────────────────────
$script:Procs = @()

function Stop-ProcessTree {
    param([int]$ProcessId)
    # taskkill /T kills the whole tree (npm -> node -> webpack-dev-server, etc.).
    # /F forces termination. Suppress all output -- best-effort cleanup.
    & taskkill.exe /F /T /PID $ProcessId 2>&1 | Out-Null
}

function Invoke-Cleanup {
    Write-Host ""
    Write-RunLog "Shutting down..."
    foreach ($p in $script:Procs) {
        try {
            if ($p -and -not $p.HasExited) {
                Stop-ProcessTree -ProcessId $p.Id
            }
        } catch {}
    }
    Write-RunOk "All processes stopped."
}

# Ctrl+C handling: rely on try/finally. PowerShell's default behavior on Ctrl+C
# raises a terminating error during Start-Sleep, which unwinds through finally
# and runs Invoke-Cleanup. Child processes (started -NoNewWindow) share the
# console process group and receive the same Ctrl+C signal, so they exit too.
$script:CancelRequested = $false

# ── Pre-flight: Python ──────────────────────────────────────────────
if ($runServer) {
    $pyOk = $false
    try {
        & $PYTHON --version *> $null
        $pyOk = ($LASTEXITCODE -eq 0)
    } catch {}
    if (-not $pyOk) {
        Write-RunErr "Python not found at: $PYTHON"
        Write-RunErr "Set OPENSTARTUP_PYTHON to your Python 3.10+ interpreter."
        exit 1
    }
    & $PYTHON -c "import fastapi, uvicorn" 2> $null
    if ($LASTEXITCODE -ne 0) {
        Write-RunWarn "Missing Python deps. Attempting: pip install fastapi uvicorn pydantic"
        & $PYTHON -m pip install --quiet fastapi uvicorn pydantic
        if ($LASTEXITCODE -ne 0) {
            Write-RunErr "Failed to install Python deps. Run manually:"
            Write-RunErr "  $PYTHON -m pip install fastapi uvicorn pydantic"
            exit 1
        }
    }
}

# ── Pre-flight: Node + ui/node_modules ──────────────────────────────
if ($runUI) {
    $nodeOk = $false
    try {
        & node --version *> $null
        $nodeOk = ($LASTEXITCODE -eq 0)
    } catch {}
    if (-not $nodeOk) {
        Write-RunErr "node not found. Install Node.js 16+ from https://nodejs.org/"
        exit 1
    }
    if (-not (Test-Path -LiteralPath (Join-Path $UI_DIR "node_modules") -PathType Container)) {
        Write-RunLog "node_modules not found - running 'npm install' (this takes a few minutes)..."
        Push-Location $UI_DIR
        try {
            & npm.cmd install
            $rc = $LASTEXITCODE
        } finally {
            Pop-Location
        }
        if ($rc -ne 0) { Write-RunErr "npm install failed."; exit 1 }
    }
}

try {
    # ── Start backend ────────────────────────────────────────────────
    if ($runServer) {
        Write-RunLog "Starting FastAPI server on ${BindHost}:${Port}..."
        $proc = Start-Process -FilePath $PYTHON `
            -ArgumentList (@("run_server.py") + $serverArgs) `
            -WorkingDirectory $SERVER_DIR `
            -NoNewWindow -PassThru
        $script:Procs += $proc
        Write-RunOk "Server PID: $($proc.Id)"
    }

    # ── Start UI (or build) ──────────────────────────────────────────
    if ($runUI) {
        if ($Build) {
            Write-RunLog "Building React UI for production..."
            Push-Location $UI_DIR
            try { & npm.cmd run build; $rc = $LASTEXITCODE }
            finally { Pop-Location }
            if ($rc -ne 0) { throw "npm run build failed (exit $rc)" }
            Write-RunOk "Production build at $UI_DIR\build"
            if (-not $runServer) {
                Write-RunLog "Tip: start with -Server to serve the built UI."
            }
        } else {
            $env:REACT_APP_BACKEND_PORT = "$Port"
            Write-RunLog "Starting React dev server on http://localhost:3000 (proxy -> :${Port})..."
            # Use npm.cmd explicitly -- Start-Process won't auto-resolve .cmd shims.
            $proc = Start-Process -FilePath "npm.cmd" `
                -ArgumentList @("start") `
                -WorkingDirectory $UI_DIR `
                -NoNewWindow -PassThru
            $script:Procs += $proc
            Write-RunOk "UI PID: $($proc.Id)"
        }
    }

    # ── Banner ───────────────────────────────────────────────────────
    if ($script:Procs.Count -gt 0) {
        Write-Host ""
        Write-RunOk "===================================================="
        Write-RunOk "  OpenStartup is running!"
        if ($runUI -and -not $Build) { Write-RunOk "  UI:     http://localhost:3000" }
        if ($runServer) {
            Write-RunOk "  API:    http://${BindHost}:${Port}"
            Write-RunOk "  Docs:   http://${BindHost}:${Port}/docs"
        }
        if ($script:RealSessionsResolved) {
            Write-RunOk "  Sessions: Real (from $($script:RealSessionsResolved))"
        }
        Write-RunOk "  Press Ctrl+C to stop all services."
        Write-RunOk "===================================================="
        Write-Host ""

        # ── Wait loop ────────────────────────────────────────────────
        # Exit when either: user pressed Ctrl+C, or any child exited.
        while (-not $script:CancelRequested) {
            Start-Sleep -Milliseconds 500
            foreach ($p in $script:Procs) {
                if ($p.HasExited) {
                    Write-RunWarn "Process PID $($p.Id) exited (rc=$($p.ExitCode)) -- stopping the rest."
                    return
                }
            }
        }
    }
} finally {
    Invoke-Cleanup
}
