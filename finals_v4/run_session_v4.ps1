param(
    [Parameter(Mandatory = $true)][string]$Setting,   # a final setting of final_plan.json: zoom_on, zoom_off, bystanders, zoom_on_repeat
    [switch]$Rehearsal,                               # development rehearsal of the setting (sessions/rehearsal_<setting>.json), not a final
    [switch]$DryRun,                                  # print every command without running it (only read-only lookups run)
    [int]$Trials = 3,                                 # rehearsal only: the number of runs (launch_prep --trials)
    [string]$UnityExe = ""                            # default: Unity Hub's editor of ProjectSettings/ProjectVersion.txt
)
# One v4 session, end to end (2026-11-13; Avatar/Config/final_procedure_v4.md). Finals run in the Unity Editor WINDOW (never
# -batchmode: it hangs before the leak test, AUDIT.md section 15), as the development sessions D2 to D4 did.
#   1. the run-protocol note (run_protocol_v4.ps1)          4. Unity in the Editor window (TrialPlayV4), waited for until it quits
#   2. launch_prep (rehearsal: --trials N)                  5. the server's exit on the disconnect (summary.json written)
#   3. the server, waited for until it says "listening"    6. rehearsal: launch_prep --cleanup; then check_session_v4.ps1 (B11)
# A FINAL is never retried and nothing is rerun: any failure stops the script, and the setting is reported as it stands. The
# final evaluation (hri_eval_final_v4.py, once only) is NOT run here: the script prints its command after a valid check.
# Server and Unity output go to new log files robot_vision\outputs\run_session_<label>_<time>_*.log (never overwritten).
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$rv = Join-Path $repo "robot_vision"
$py = Join-Path $rv ".venv\Scripts\python.exe"
$project = Join-Path $repo "unity\Robotics-Warehouse\WarehouseProjectURP"
$kind = if ($Rehearsal) { "rehearsal" } else { "final" }
$label = "${kind}_$Setting"
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$step = 0
function Say($text) { Write-Host $text }
function Stop-Session($why) { Say "STOPPED: $why"; if (-not $Rehearsal -and $script:serverStarted) { Say "A final was started: do not rerun it. Report the setting as it stands (AUDIT.md section 15)." }; exit 1 }
function Step($title, $show) { $script:step++; Say ""; Say "[$script:step] $title"; foreach ($l in @($show) | Where-Object { $_ }) { Say "    $l" } }
function Q($s) { if ($s -match '\s') { "`"$s`"" } else { $s } }

# ---- read-only lookups (also in -DryRun): the setting, its control file, the numbers and paths from the configs
$plan = Get-Content (Join-Path $rv "configs\v4\final_plan.json") -Raw | ConvertFrom-Json
$names = @($plan.settings.PSObject.Properties.Name)
if ($names -notcontains $Setting) { Say "REFUSED: unknown setting '$Setting'; final_plan.json has $($names -join ', ')"; exit 2 }
$trialsCfg = Get-Content (Join-Path $rv "configs\trials.json") -Raw | ConvertFrom-Json
$outputs = Join-Path $rv $trialsCfg.output_root
Push-Location $rv
try { $control = (& $py -c "from bridge.server import FINAL_CONTROL as F; print(F['$Setting'])").Trim() } finally { Pop-Location }
if ($LASTEXITCODE -ne 0 -or -not $control) { Say "REFUSED: no control file for '$Setting' (bridge/server.py FINAL_CONTROL)"; exit 2 }
$unityVersion = ((Get-Content (Join-Path $project "ProjectSettings\ProjectVersion.txt")) -match '^m_EditorVersion:' -replace '^m_EditorVersion:\s*', '')[0]
if (-not $UnityExe) { $UnityExe = Join-Path $env:ProgramFiles "Unity\Hub\Editor\$unityVersion\Editor\Unity.exe" }
if (-not (Test-Path $UnityExe)) { Say "REFUSED: Unity editor not found at $UnityExe (give -UnityExe)"; exit 2 }
if ($Rehearsal) {
    if ($Trials -lt 1) { Say "REFUSED: -Trials must be at least 1"; exit 2 }
    $workers = "Assets/WarehouseRobot/Avatar/Config/sessions/rehearsal_$Setting.json"
    if (-not (Test-Path (Join-Path $project $workers))) { Say "REFUSED: no rehearsal config $workers for '$Setting'"; exit 2 }
    $timeout = (Get-Content (Join-Path $project "Assets\WarehouseRobot\Scenario\Config\trial_plan_v4.json") -Raw | ConvertFrom-Json).development_timeout_s
    $runs = $Trials
    $unityMode = @("-workersConfig", $workers)
    $sessionPattern = "trials_development_$($trialsCfg.task)_*"
} else {
    if ($PSBoundParameters.ContainsKey("Trials")) { Say "REFUSED: -Trials is for a rehearsal only (a final runs runs_per_setting = $($plan.runs_per_setting))"; exit 2 }
    $timeout = $plan.timeout_s
    $runs = [int]$plan.runs_per_setting
    $unityMode = @("-finalSetting", $Setting)
    $sessionPattern = "trials_final_$($plan.task)_${Setting}_*"
}
$trialTimeout = [int]($runs * $timeout + 1800)
$serverArgs = @("-u", "-m", "bridge.server", "--mode", "guide", "--task", $plan.task, "--perception", "vision", "--config", "configs/v4/bridge.json",
                "--control-config", $control) + $(if ($Rehearsal) { @() } else { @("--final-setting", $Setting) }) + @("--resource-log", "--exit-on-disconnect")
$serverOut = Join-Path $outputs "run_session_${label}_${stamp}_server.log"
$serverErr = Join-Path $outputs "run_session_${label}_${stamp}_server.err.log"
$unityLog = Join-Path $outputs "run_session_${label}_${stamp}_unity.log"
$unityArgs = @("-projectPath", (Q $project), "-executeMethod", "WarehouseRobot.ScenarioEditor.TrialPlayV4.Run") + $unityMode + @("-trialTimeout", $trialTimeout, "-logFile", (Q $unityLog))
Say "v4 session: $kind of setting $Setting, $runs runs, timeout $timeout s per run, Unity $unityVersion in the Editor window$(if ($DryRun) { ' (DRY RUN: nothing is run)' })"

# ---- checks before anything is written
Step "checks before the session" @(
    "git branch, tracked changes; no Unity Editor running; no robot_vision\configs\trials.local.json (final); no earlier run of the setting (final)",
    $(if (-not $Rehearsal) { "cd robot_vision; $py -c `"from bridge import server as S; S.preflight_final(S.load_config('configs/v4/bridge.json')[0], 'guide', '$Setting', '$control')`"" }))
if (-not $DryRun) {
    $branch = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
    $dirty = @(git -C $repo status --porcelain --untracked-files=no)
    if (Get-Process -Name "Unity" -ErrorAction SilentlyContinue) { Stop-Session "a Unity Editor is running: close it first (the session opens the project itself)" }
    if ($Rehearsal) {
        if ($branch -ne "main" -or $dirty.Count) { Say "    note: branch $branch, $($dirty.Count) tracked change(s) (the procedure rehearses on an up-to-date main)" }
    } else {
        if ($branch -ne "main") { Stop-Session "a final runs on main (branch is $branch)" }
        if ($dirty.Count) { Stop-Session "a final needs a clean tree: $($dirty -join '; ')" }
        if (Test-Path (Join-Path $rv "configs\trials.local.json")) { Stop-Session "robot_vision\configs\trials.local.json exists (development override): a final is refused" }
        $unityDone = @(Get-ChildItem $outputs -Directory | ForEach-Object { Join-Path $_.FullName "UNITY_FINAL_DONE.json" } | Where-Object { Test-Path $_ } |
                       Where-Object { (Get-Content $_ -Raw | ConvertFrom-Json).final_setting -eq $Setting })
        if ($unityDone.Count) { Stop-Session "setting $Setting was already run in Unity: $($unityDone[0])" }
        Push-Location $rv
        try {
            $ErrorActionPreference = "Continue"
            $pre = & $py -c "from bridge import server as S; S.preflight_final(S.load_config('configs/v4/bridge.json')[0], 'guide', '$Setting', '$control')" 2>&1
            $preOk = ($LASTEXITCODE -eq 0)
            $ErrorActionPreference = "Stop"
        } finally { Pop-Location }
        if (-not $preOk) { Stop-Session "the server's final preflight refuses: $($pre -join ' ')" }
    }
    foreach ($f in $serverOut, $serverErr, $unityLog) { if (Test-Path $f) { Stop-Session "$f exists; not overwritten" } }
    Say "    ok: branch $branch, clean tracked tree $($dirty.Count -eq 0)"
}

# ---- 1. the run-protocol note
Step "run-protocol note (free memory, programs running, power scheme, commit)" "$repo\finals_v4\run_protocol_v4.ps1 -Label $label"
$note = "<the note's path>"
if (-not $DryRun) {
    $noteOut = @(& (Join-Path $PSScriptRoot "run_protocol_v4.ps1") -Label $label)
    $noteOut | Select-Object -SkipLast 1 | ForEach-Object { Say $_ }
    $note = [string]$noteOut[-1]
    if (-not (Test-Path $note)) { Stop-Session "the protocol note was not written" }
    Say "    note: $note"
}

# ---- 2. launch_prep (task check, machine state; rehearsal: the trial-count override)
$prepArgs = @("launch_prep.py", "--task", $plan.task) + $(if ($Rehearsal) { @("--trials", $Trials) } else { @() })
Step "launch_prep" "cd robot_vision; $py $($prepArgs -join ' ')"
$prepWritten = $false
if (-not $DryRun) {
    Push-Location $rv
    try { & $py @prepArgs; $prepOk = ($LASTEXITCODE -eq 0) } finally { Pop-Location }
    if (-not $prepOk) { Stop-Session "launch_prep refused" }
    $prepWritten = [bool]$Rehearsal
}

$status = 1
try {
    # ---- 3. the server
    Step "server (output to $serverOut), waited for until it says listening" "cd robot_vision; `$env:PYTHONIOENCODING = 'utf-8'; $py $($serverArgs -join ' ')"
    $bridge = "<the bridge run folder>"
    if (-not $DryRun) {
        $env:PYTHONIOENCODING = "utf-8"
        $server = Start-Process -FilePath $py -ArgumentList $serverArgs -WorkingDirectory $rv -NoNewWindow -PassThru `
                                -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr
        $null = $server.Handle                              # keeps the exit code readable after the exit
        $script:serverStarted = $true
        $deadline = (Get-Date).AddSeconds(900)
        while ($true) {
            $line = Select-String -Path $serverOut -Pattern "listening on .*; run folder (.+)$" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($line) { $bridge = $line.Matches[0].Groups[1].Value.Trim(); break }
            if ($server.HasExited) { $script:serverStarted = $false; Get-Content $serverOut, $serverErr -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Say "    $_" }; Stop-Session "the server exited before listening (nothing was run)" }
            if ((Get-Date) -gt $deadline) { Stop-Session "the server did not say listening within 900 s (PID $($server.Id) left running; stop it with Ctrl+C in its window or Stop-Process)" }
            Start-Sleep -Seconds 1
        }
        Say "    listening; bridge run folder $bridge"
    }

    # ---- 4. Unity in the Editor window
    Step "Unity in the Editor window (no -batchmode), waited for until it quits (up to $trialTimeout s)" "$(Q $UnityExe) $($unityArgs -join ' ')"
    $started = Get-Date
    if (-not $DryRun) {
        $unity = Start-Process -FilePath $UnityExe -ArgumentList $unityArgs -PassThru
        $null = $unity.Handle
        $unity.WaitForExit()
        $finished = Select-String -Path $unityLog -Pattern "\[TrialPlayV4\] finished" -ErrorAction SilentlyContinue | Select-Object -Last 1
        Say "    Unity exit code $($unity.ExitCode): $(if ($finished) { $finished.Line.Trim() } else { 'no [TrialPlayV4] finished line in ' + $unityLog })"
        $refused = Select-String -Path $unityLog -Pattern "refused:" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($refused) { Say "    $($refused.Line.Trim())" }
    }

    # ---- 5. the server's exit on the disconnect
    Step "the server exits on the disconnect and writes summary.json (waited for up to 300 s)" "(wait for the server process)"
    if (-not $DryRun) {
        if (-not $server.WaitForExit(300000)) {
            Stop-Session "the server (PID $($server.Id)) did not exit after Unity quit; stop it by hand (summary.json is written on a clean stop), then run check_session_v4.ps1 yourself"
        }
        Say "    server exited ($(if (Test-Path (Join-Path $bridge 'summary.json')) { 'summary.json written' } else { 'NO summary.json' }))"
    }
    $status = 0
} finally {
    # ---- 6a. rehearsal: remove the trial-count override (also after a failure)
    if ($Rehearsal) {
        Step "launch_prep --cleanup (rehearsal)" "cd robot_vision; $py launch_prep.py --cleanup"
        if ($prepWritten) { Push-Location $rv; try { & $py launch_prep.py --cleanup } finally { Pop-Location } }
    }
}
if ($status -ne 0) { exit 1 }

# ---- 6b. the B11 check
$session = "<the new $sessionPattern folder>"
if (-not $DryRun) {
    $found = @(Get-ChildItem $outputs -Directory -Filter $sessionPattern | Where-Object { $_.CreationTime -ge $started.AddSeconds(-5) })
    if ($found.Count -ne 1) { Stop-Session "expected one new $sessionPattern folder, found $($found.Count): run check_session_v4.ps1 yourself" }
    $session = $found[0].FullName
}
$checkArgs = @("-U", (Q $session), "-B", (Q $bridge), "-Runs", $runs) + $(if ($Rehearsal) { @() } else { @("-Final") }) + @("-Protocol", (Q $note))
Step "B11 validity check" "$repo\finals_v4\check_session_v4.ps1 $($checkArgs -join ' ')"
if ($DryRun) {
    if (-not $Rehearsal) {
        Step "afterwards, by hand, once and only if the check says SESSION VALID: the final evaluation" "cd robot_vision; $py hri_eval_final_v4.py --setting $Setting --session <session> <bridge>"
    }
    Say ""; Say "DRY RUN: nothing was run."; exit 0
}
& (Join-Path $PSScriptRoot "check_session_v4.ps1") -U $session -B $bridge -Runs $runs -Final:(-not $Rehearsal) -Protocol $note | ForEach-Object { Say "    $_" }
$valid = ($LASTEXITCODE -eq 0)
Say ""
Say "Unity session: $session"
Say "bridge run:    $bridge"
Say "protocol note: $note"
Say "logs:          $serverOut, $unityLog"
if ($Rehearsal) {
    Say $(if ($valid) { "REHEARSAL VALID (development data; not a result)." } else { "REHEARSAL INVALID: fix the cause before any final." })
} elseif ($valid) {
    Say "FINAL $Setting VALID. Next, once (it writes FINAL_DONE.json and cannot be repeated), from robot_vision\:"
    Say "    $py hri_eval_final_v4.py --setting $Setting --session `"$session`" `"$bridge`""
} else {
    Say "FINAL $Setting INVALID: report it as invalid with the reasons above. It is never rerun and not evaluated."
}
exit $(if ($valid) { 0 } else { 1 })
