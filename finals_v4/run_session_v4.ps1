param(
    [string]$Experiment = "",                         # experiments A/B (the final study since 2026-11-14): A1, A2, A3, A4, B1, B2, B3, B4
    [string]$Side = "",                               # A2 / B2 only (the turn map): right or left; the final setting is <Experiment>_<Side>
    [string]$Setting = "",                            # SUPERSEDED (refused): the v4 Task 2 settings zoom_on, zoom_off, bystanders, zoom_on_repeat
    [switch]$Rehearsal,                               # development rehearsal of a final setting (TrialPlayV4 -experiment, development looks and clips)
    [switch]$DryRun,                                  # print every command without running it (only read-only lookups run)
    [int]$Trials = 3,                                 # rehearsal only: the number of runs (launch_prep --trials)
    [string]$UnityExe = ""                            # default: Unity Hub's editor of ProjectSettings/ProjectVersion.txt
)
# One v4 session, end to end (2026-11-13; Avatar/Config/final_procedure_v4.md). Since 2026-11-14 the finals are the experiments A/B
# (Avatar/Config/experiments_ab.md section 7): -Experiment A1..B4, with -Side right|left for A2 and B2; the setting must be one of the
# final matrix (Avatar/Config/final_v4.json settings), whose final config (sessions/final_ab_<setting>.json) names the Python control file.
# The Task 2 settings (-Setting) are superseded and refused. Finals run in the Unity Editor WINDOW (never -batchmode: it hangs before the
# leak test, AUDIT.md section 15), as the development sessions D2 to D4 did.
#   1. the run-protocol note (run_protocol_v4.ps1)          4. Unity in the Editor window (TrialPlayV4), waited for until it quits
#   2. launch_prep (rehearsal: --trials N)                  5. the server's exit on the disconnect (summary.json written)
#   3. the server, waited for until it says "listening"    6. rehearsal: launch_prep --cleanup; then check_session_v4.ps1 (B11)
# A FINAL is never retried and nothing is rerun: any failure stops the script, and the setting is reported as it stands. The
# setting's final evaluation and CSV export (Anisha's tools, once only) are NOT run here: the script prints them after a valid check.
# -DryRun also lists every reason a real run would be refused right now (read-only lookups).
# Server and Unity output go to new log files robot_vision\outputs\run_session_<label>_<time>_*.log (never overwritten).
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$rv = Join-Path $repo "robot_vision"
$py = Join-Path $rv ".venv\Scripts\python.exe"
$project = Join-Path $repo "unity\Robotics-Warehouse\WarehouseProjectURP"
$assets = Join-Path $project "Assets\WarehouseRobot"
$kind = if ($Rehearsal) { "rehearsal" } else { "final" }
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$step = 0
function Say($text) { Write-Host $text }
function Stop-Session($why) { Say "STOPPED: $why"; if (-not $Rehearsal -and $script:serverStarted) { Say "A final was started: do not rerun it. Report the setting as it stands (experiments_ab.md section 7)." }; exit 1 }
function Step($title, $show) { $script:step++; Say ""; Say "[$script:step] $title"; foreach ($l in @($show) | Where-Object { $_ }) { Say "    $l" } }
function Q($s) { if ($s -match '\s') { "`"$s`"" } else { $s } }
function Json($path) { Get-Content $path -Raw | ConvertFrom-Json }
function Marker($folderRoot, $file, $key, $value) {
    @(Get-ChildItem $folderRoot -Directory -ErrorAction SilentlyContinue | ForEach-Object { Join-Path $_.FullName $file } | Where-Object { Test-Path $_ } |
      Where-Object { (Json $_).$key -eq $value })
}

# ---- the setting (read-only lookups, also in -DryRun)
if ($Setting) {
    Say "REFUSED: -Setting $Setting is superseded: the v4 Task 2 finals (zoom_on, zoom_off, bystanders, zoom_on_repeat) were replaced by the experiments A/B on 2026-11-14 (final_v4.json superseded_settings; experiments_ab.md section 7). Use -Experiment A1..B4 [-Side right|left]."
    exit 2
}
if ($Experiment -notmatch '^[AB][1-4]$') { Say "REFUSED: give -Experiment A1, A2, A3, A4, B1, B2, B3 or B4 (and -Side right|left for A2 and B2)"; exit 2 }
$ecfg = Json (Join-Path $assets "Scenario\Config\experiments_ab_unity.json")
$edef = @($ecfg.experiments | Where-Object { $_.name -eq $Experiment })
if ($edef.Count -ne 1) { Say "REFUSED: experiment $Experiment is not in experiments_ab_unity.json"; exit 2 }
$map = (Json (Join-Path $repo $ecfg.scenarios_ab)).scenarios.($edef[0].scenario).map
if ($map -eq "turn") {
    if (@("right", "left") -notcontains $Side) { Say "REFUSED: $Experiment runs on the turn map: give -Side right or left"; exit 2 }
} elseif ($Side) { Say "REFUSED: -Side is for the turn experiments (A2, B2) only; $Experiment uses the map $map"; exit 2 }
$name = if ($Side) { "${Experiment}_$Side" } else { $Experiment }
$finalCfg = Json (Join-Path $assets "Avatar\Config\final_v4.json")
$fset = @($finalCfg.settings | Where-Object { $_.name -eq $name })
if ($fset.Count -ne 1) { Say "REFUSED: '$name' is not a setting of the final matrix (final_v4.json settings: $(@($finalCfg.settings | ForEach-Object name) -join ', '))"; exit 2 }
$fexp = Json (Join-Path $project $fset[0].experiment_config)
$control = $fexp.python_control
if (-not $control -or -not (Test-Path (Join-Path $rv $control))) { Say "REFUSED: the control file '$control' of $($fset[0].experiment_config) does not exist under robot_vision\"; exit 2 }
$label = "${kind}_$name"
$plan = Json (Join-Path $rv "configs\v4\final_plan.json")
$trialsCfg = Json (Join-Path $rv "configs\trials.json")
$outputs = Join-Path $rv $trialsCfg.output_root
$unityVersion = ((Get-Content (Join-Path $project "ProjectSettings\ProjectVersion.txt")) -match '^m_EditorVersion:' -replace '^m_EditorVersion:\s*', '')[0]
if (-not $UnityExe) { $UnityExe = Join-Path $env:ProgramFiles "Unity\Hub\Editor\$unityVersion\Editor\Unity.exe" }
if (-not (Test-Path $UnityExe)) { Say "REFUSED: Unity editor not found at $UnityExe (give -UnityExe)"; exit 2 }
if ($Rehearsal) {
    if ($Trials -lt 1) { Say "REFUSED: -Trials must be at least 1"; exit 2 }
    $timeout = (Json (Join-Path $assets "Scenario\Config\trial_plan_v4.json")).development_timeout_s
    $runs = $Trials
    $unityMode = @("-experiment", $Experiment) + $(if ($Side) { @("-experimentSide", $Side) } else { @() })
    $sessionPattern = "trials_development_$($trialsCfg.task)_${Experiment}_*"
} else {
    if ($PSBoundParameters.ContainsKey("Trials")) { Say "REFUSED: -Trials is for a rehearsal only (a final runs runs_per_setting = $($plan.runs_per_setting))"; exit 2 }
    $timeout = $plan.timeout_s
    $runs = [int]$plan.runs_per_setting
    $unityMode = @("-finalSetting", $name)
    $sessionPattern = "trials_final_$($plan.task)_${name}_*"
}

# ---- what would refuse a real run right now (read-only)
$blockers = @()
$notes = @()
$branch = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
$dirty = @(git -C $repo status --porcelain --untracked-files=no)
if (Get-Process -Name "Unity" -ErrorAction SilentlyContinue) { $blockers += "a Unity Editor is running: close it first (the session opens the project itself)" }
if ($Rehearsal) {
    if ($branch -ne "main" -or $dirty.Count) { $notes += "branch $branch, $($dirty.Count) tracked change(s) (the procedure rehearses on an up-to-date main)" }
} else {
    if ($branch -ne "main") { $blockers += "a final runs on main (branch is $branch)" }
    if ($dirty.Count) { $blockers += "a final needs a clean tree: $($dirty -join '; ')" }
    if (Test-Path (Join-Path $rv "configs\trials.local.json")) { $blockers += "robot_vision\configs\trials.local.json exists (development override): a final is refused" }
    $unityDone = Marker $outputs "UNITY_FINAL_DONE.json" "final_setting" $name
    if ($unityDone.Count) { $blockers += "setting $name was already run in Unity: $($unityDone[0])" }
    $pyDone = Marker $outputs "FINAL_RUN_DONE.json" "setting" $name
    if ($pyDone.Count) { $blockers += "setting $name was already run by the server: $($pyDone[0])" }
    if (@($plan.settings.PSObject.Properties.Name) -notcontains $name) { $blockers += "Python's configs/v4/final_plan.json has no setting '$name' (Anisha adds the final matrix)" }
    Push-Location $rv
    try {
        $ErrorActionPreference = "Continue"
        $pyControl = [string](& $py -c "from bridge.server import FINAL_CONTROL as F; print(F.get('$name', ''))" 2>$null)
        $pyOk = ($LASTEXITCODE -eq 0)
        $ErrorActionPreference = "Stop"
    } finally { Pop-Location }
    $pyControl = $pyControl.Trim()
    if (-not $pyOk) { $blockers += "bridge/server.py FINAL_CONTROL could not be read" }
    elseif (-not $pyControl) { $blockers += "bridge/server.py FINAL_CONTROL has no '$name' (Anisha adds it: $control)" }
    elseif ($pyControl -ne $control) { $blockers += "bridge/server.py FINAL_CONTROL names $pyControl for '$name', the Unity final config $control" }
    if (-not (Json (Join-Path $rv "configs\v4\frozen.json")).frozen) { $blockers += "configs/v4/frozen.json is not frozen (Nusrat runs freeze_v4.py --freeze by hand after Anisha's final_plan.json entries)" }
}

$trialTimeout = [int]($runs * $timeout + 1800)
$serverArgs = @("-u", "-m", "bridge.server", "--mode", "guide", "--task", $plan.task, "--perception", "vision", "--config", "configs/v4/bridge.json",
                "--control-config", $control) + $(if ($Rehearsal) { @() } else { @("--final-setting", $name) }) + @("--resource-log", "--exit-on-disconnect")
$serverOut = Join-Path $outputs "run_session_${label}_${stamp}_server.log"
$serverErr = Join-Path $outputs "run_session_${label}_${stamp}_server.err.log"
$unityLog = Join-Path $outputs "run_session_${label}_${stamp}_unity.log"
$unityArgs = @("-projectPath", (Q $project), "-executeMethod", "WarehouseRobot.ScenarioEditor.TrialPlayV4.Run") + $unityMode + @("-trialTimeout", $trialTimeout, "-logFile", (Q $unityLog))
Say "v4 session: $kind of setting $name (experiment $Experiment, map $map$(if ($Side) { ", $Side turn" }), lie detection $($fexp.lie_detection)), $runs runs, timeout $timeout s per run, Unity $unityVersion in the Editor window$(if ($DryRun) { ' (DRY RUN: nothing is run)' })"
Say "    $(if ($Rehearsal) { 'development looks and clips of data_splits.json, seed dev_seed of trials.json' } else { "test looks $(@($fexp.male_looks) + @($fexp.female_looks) -join ', '), test clips $(@($fexp.point_clips) + @($fexp.proceed_clips) -join ', '), seed final_seed $($plan.final_seed) of final_plan.json" }); control $control"

# ---- checks before anything is written
Step "checks before the session" @(
    "git branch, tracked changes; no Unity Editor running$(if (-not $Rehearsal) { '; no trials.local.json; no earlier run of the setting (UNITY_FINAL_DONE.json, FINAL_RUN_DONE.json); final_plan.json and FINAL_CONTROL know the setting; frozen' })",
    $(if (-not $Rehearsal) { "cd robot_vision; $py -c `"from bridge import server as S; S.preflight_final(S.load_config('configs/v4/bridge.json')[0], 'guide', '$name', '$control')`"" }))
foreach ($n in $notes) { Say "    note: $n" }
if ($DryRun) {
    if ($blockers.Count) { Say "    a real run would be REFUSED now:"; foreach ($b in $blockers) { Say "      - $b" } } else { Say "    a real run would pass these checks now (the server's preflight is not run in a dry run)" }
} else {
    if ($blockers.Count) { Stop-Session ($blockers -join "; ") }
    if (-not $Rehearsal) {
        Push-Location $rv
        try {
            $ErrorActionPreference = "Continue"
            $pre = & $py -c "from bridge import server as S; S.preflight_final(S.load_config('configs/v4/bridge.json')[0], 'guide', '$name', '$control')" 2>&1
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
$evaluation = @("the setting's final evaluation and CSV export, Anisha's tools, run once (their final mode for the experiments is pending: outputs\for_anisha_finals_ab_*.md), e.g.",
                "cd robot_vision; $py hri_eval_final_v4.py --setting $name --session $(Q $session) $(Q $bridge)",
                "cd robot_vision; $py export_csv_v4.py --session $(Q $session) $(Q $bridge)")
if ($DryRun) {
    if (-not $Rehearsal) { Step "afterwards, by hand, once and only if the check says SESSION VALID" $evaluation }
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
    Say "FINAL $name VALID. Next, once (each writes its run-once marker and cannot be repeated):"
    foreach ($l in $evaluation) { Say "    $l" }
} else {
    Say "FINAL $name INVALID: report it as invalid with the reasons above. It is never rerun and not evaluated."
}
exit $(if ($valid) { 0 } else { 1 })
