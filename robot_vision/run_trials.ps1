<#
.SYNOPSIS
  Trial launcher (Windows): starts the bridge server in GUIDE mode with VISION perception for one task.

.DESCRIPTION
  The only supported way to run trials. It always runs
      python -m bridge.server --mode guide --perception vision --task <Task>
  from robot_vision\.venv (hello mode, a 0.2 m/s bridge test, is never used here). It refuses to start when
  configs\trials.json (or the git-ignored trials.local.json the Unity trial runner prefers) names another task,
  because the Unity trial runner would then refuse the map.

  Without -UnityBatch: the server runs in this window; press Play in the Unity Editor (scene
  Assets/Scenes/WarehouseRobot.unity); Ctrl+C stops the server after the session.
  With -UnityBatch: also runs the whole session headless (TrialBatchPlay), stops the server when Unity quits, then
  merges the logs (hri_trials.py), summarises them (hri_analysis.py) and checks the session (hri_session_check.py).

.EXAMPLE
  .\run_trials.ps1 -Task Task1
.EXAMPLE
  .\run_trials.ps1 -Task Task1 -UnityBatch
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet("Task1", "Task2")][string]$Task,
    [switch]$UnityBatch,
    [string]$UnityPath = $env:UNITY_EDITOR,
    [int]$TrialTimeoutS = 3600
)
$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$Python = Join-Path $Here ".venv\Scripts\python.exe"
$Project = [System.IO.Path]::GetFullPath((Join-Path $Here "..\unity\Robotics-Warehouse\WarehouseProjectURP"))
if (-not (Test-Path $Python)) { Write-Error "No project venv at $Python (see README: create robot_vision\.venv first)." }

# The Unity trial runner reads trials.local.json if present, else trials.json; its task must be this task.
$TrialsFile = Join-Path $Here "configs\trials.local.json"
if (-not (Test-Path $TrialsFile)) { $TrialsFile = Join-Path $Here "configs\trials.json" }
$Trials = Get-Content -Raw -Encoding UTF8 $TrialsFile | ConvertFrom-Json
if ($Trials.task -ne $Task) {
    Write-Error "$TrialsFile says task '$($Trials.task)' but you asked for $Task. Set ""task"" there (and ""mode"") first."
}
Write-Host "[run_trials] GUIDE mode, VISION perception, task $Task ($($Trials.mode), $(Split-Path -Leaf $TrialsFile))"

$ServerArgs = @("-m", "bridge.server", "--mode", "guide", "--perception", "vision", "--task", $Task)
Push-Location $Here
try {
    if (-not $UnityBatch) {
        Write-Host "[run_trials] when the server says 'listening', press Play in Unity. Ctrl+C stops the server."
        & $Python @ServerArgs
        exit $LASTEXITCODE
    }

    if (-not $UnityPath) {
        $Version = ((Get-Content (Join-Path $Project "ProjectSettings\ProjectVersion.txt"))[0] -split ":\s*")[1].Trim()
        $UnityPath = Join-Path $env:ProgramFiles "Unity\Hub\Editor\$Version\Editor\Unity.exe"
    }
    if (-not (Test-Path $UnityPath)) { Write-Error "Unity not found at $UnityPath (set -UnityPath or `$env:UNITY_EDITOR)." }
    $Started = Get-Date
    $Server = Start-Process -FilePath $Python -ArgumentList ($ServerArgs + "--exit-on-disconnect") -NoNewWindow -PassThru
    $UnityLog = Join-Path ([System.IO.Path]::GetTempPath()) ("unity_trials_{0:yyyyMMdd_HHmmss}.log" -f $Started)
    Write-Host "[run_trials] Unity batch session (log $UnityLog); the server warms up first, Unity waits for it."
    $Unity = Start-Process -FilePath $UnityPath -NoNewWindow -PassThru -Wait -ArgumentList @(
        "-batchmode", "-projectPath", "`"$Project`"", "-executeMethod", "WarehouseRobot.ScenarioEditor.TrialBatchPlay.Run",
        "-trialTimeout", "$TrialTimeoutS", "-logFile", "`"$UnityLog`"")
    Write-Host "[run_trials] Unity exited with $($Unity.ExitCode)"
    if (-not $Server.WaitForExit(120000)) { Write-Warning "server still running; stopping it"; Stop-Process -Id $Server.Id }

    $Out = Join-Path $Here "outputs"
    $TrialsDir = Get-ChildItem $Out -Directory -Filter "trials_*_$Task*" | Where-Object { $_.CreationTime -ge $Started } |
        Sort-Object CreationTime | Select-Object -Last 1
    $BridgeDir = Get-ChildItem $Out -Directory -Filter "bridge_guide_*" | Where-Object { $_.CreationTime -ge $Started } |
        Sort-Object CreationTime | Select-Object -Last 1
    if (-not $TrialsDir -or -not $BridgeDir) { Write-Error "no new trials_* / bridge_guide_* folder under $Out" }
    Write-Host "[run_trials] Unity: outputs\$($TrialsDir.Name)  Python: outputs\$($BridgeDir.Name)"
    & $Python hri_trials.py --unity "outputs/$($TrialsDir.Name)" --bridge "outputs/$($BridgeDir.Name)" | Select-Object -Last 1
    $Merged = Get-ChildItem $Out -Directory -Filter "hri_trials_*" | Sort-Object CreationTime | Select-Object -Last 1
    & $Python hri_analysis.py "outputs/$($Merged.Name)" | Select-Object -Last 1
    & $Python hri_session_check.py --unity "outputs/$($TrialsDir.Name)" --bridge "outputs/$($BridgeDir.Name)"
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
