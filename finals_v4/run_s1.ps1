param(
    [string]$Character = "",          # mixamo_worker | anime_f_01 | anime_f_02_outfit_short | cartoon_boxo_01
    [string]$Setting = "",            # A1 | A3 | B3
    [switch]$All,                     # the 12 cells in the fixed order of s1_supplementary.json cell_order (finished cells are skipped; a started, unfinished cell stops the run)
    [switch]$Resume,                  # resume ONE interrupted cell, once (AUDIT.md 16.30.1 as for the finals); with -Character and -Setting
    [switch]$Plan,                    # print the 60-run plan (character, setting, run, goal, liars) from Unity in batch mode (no Play, no server, no perception) and stop
    [switch]$DryRun,                  # print every step and every refusal without running anything (read-only lookups only)
    [string]$UnityExe = ""            # default: Unity Hub's editor of ProjectSettings/ProjectVersion.txt
)
# The post-freeze supplementary experiment S1 (Anisha's AUDIT.md 16.36 and 16.37; Unity addendum 14 of Avatar/Config/experiments_ab.md, declared
# 2026-11-25 before any S1 run). One CELL = one character x one setting (A1, A3 or B3) = one Unity session of 5 runs (the plan runs of the final plan,
# seed 2, timeout 480 s) with its own bridge server, in the Unity Editor WINDOW (never -batchmode: it hangs before the leak test, AUDIT.md section 15).
# EXPLORATORY: never pooled with the finals; no frozen match is required and no FINAL_* marker is written (S1 keeps its own markers in the session folder).
#   1. the run-protocol note (run_protocol_v4.ps1)           5. Unity in the Editor window (TrialPlayV4 -s1Character -s1Setting), watched
#   2. launch_prep                                           6. the server's exit on the disconnect (summary.json)
#   3. the server with the setting's control file            7. check_s1_session.ps1 (validity only), the entry of robot_vision\outputs\s1_runs.json
#   4. (cell markers: S1CellGuard in Unity refuses a cell that was started before)
# Same run protocol as the finals: other apps closed (Claude, VS Code, browsers), Best performance, NEVER from the VS Code terminal (refused here).
# A transcript of every call is written to robot_vision\outputs\run_s1_<label>_<time>_transcript.log; a crash watch (server or Unity dying, Event Viewer
# application errors) to ..._crashwatch.log (both .log: the Python test test_run_paths refuses absolute paths in the .txt/.json/.csv files under outputs\). There is no run_finals_sitting.ps1 in the repository: the crash watch, the transcript and the app check are
# made here (addendum 14).
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$rv = Join-Path $repo "robot_vision"
$py = Join-Path $rv ".venv\Scripts\python.exe"
$project = Join-Path $repo "unity\Robotics-Warehouse\WarehouseProjectURP"
$assets = Join-Path $project "Assets\WarehouseRobot"
function Say($text) { Write-Host $text }
function Q($s) { if ($s -match '\s') { "`"$s`"" } else { $s } }
function Json($path) { Get-Content $path -Raw | ConvertFrom-Json }
$s1 = Json (Join-Path $assets "Avatar\Config\s1_supplementary.json")
$finalCfg = Json (Join-Path $assets "Avatar\Config\final_v4.json")
$finalPlan = Json (Join-Path $rv "configs\v4\final_plan.json")
$trialsCfg = Json (Join-Path $rv "configs\trials.json")
$outputs = Join-Path $rv $trialsCfg.output_root
$unityVersion = ((Get-Content (Join-Path $project "ProjectSettings\ProjectVersion.txt")) -match '^m_EditorVersion:' -replace '^m_EditorVersion:\s*', '')[0]
if (-not $UnityExe) { $UnityExe = Join-Path $env:ProgramFiles "Unity\Hub\Editor\$unityVersion\Editor\Unity.exe" }
$runsPerCell = [int]$s1.runs_per_cell
$timeout = [int]$s1.timeout_s
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

# ---- the cells
$cells = @()
if ($All) {
    if ($Character -or $Setting -or $Resume) { Say "REFUSED: -All takes no -Character, -Setting or -Resume"; exit 2 }
    $cells = @($s1.cell_order | ForEach-Object { [pscustomobject]@{ Character = $_.character; Setting = $_.setting } })
} elseif ($Plan) {
    $cells = @()
} else {
    if (@($s1.characters) -notcontains $Character) { Say "REFUSED: -Character must be one of $(@($s1.characters) -join ', ') (or give -All)"; exit 2 }
    if (@($s1.settings | ForEach-Object name) -notcontains $Setting) { Say "REFUSED: -Setting must be one of $(@($s1.settings | ForEach-Object name) -join ', ')"; exit 2 }
    $cells = @([pscustomobject]@{ Character = $Character; Setting = $Setting })
}

# ---- Unity in batch mode: the plan table (nothing is run)
if ($Plan) {
    $planOut = "robot_vision/outputs/s1_plan_$stamp.txt"
    $planArgs = @("-batchmode", "-quit", "-projectPath", (Q $project), "-executeMethod", "WarehouseAvatar.EditorTools.S1PlanCheck.PrintBatch", "-s1PlanOut", $planOut,
                  "-logFile", (Q (Join-Path $outputs "run_s1_plan_${stamp}_unity.log")))
    Say "S1 plan only: $(Q $UnityExe) $($planArgs -join ' ')"
    if ($DryRun) { Say "DRY RUN: nothing was run."; exit 0 }
    $u = Start-Process -FilePath $UnityExe -ArgumentList $planArgs -PassThru -Wait
    if (Test-Path (Join-Path $repo $planOut)) { Get-Content (Join-Path $repo $planOut) | ForEach-Object { Say $_ } } else { Say "no plan file was written: see $(Join-Path $outputs "run_s1_plan_${stamp}_unity.log")" }
    exit $u.ExitCode
}

# ---- what a real run would be refused for right now (read-only)
$blockers = @()
$notes = @()
if ($env:TERM_PROGRAM -eq "vscode" -or $env:VSCODE_PID -or $env:VSCODE_INJECTION -or $env:VSCODE_GIT_IPC_HANDLE) { $blockers += "this is a VS Code terminal: run S1 from a plain PowerShell window (run protocol)" }
$apps = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { @("chrome", "msedge", "firefox", "Code", "claude", "Claude") -contains $_.ProcessName } | Group-Object ProcessName | ForEach-Object { "$($_.Name) x$($_.Count)" })
if ($apps.Count) { $blockers += "close these programs first (run protocol): $($apps -join ', ')" }
foreach ($u in @(Get-Process -Name "Unity" -ErrorAction SilentlyContinue)) {
    $c = Get-CimInstance Win32_Process -Filter "ProcessId=$($u.Id)" -ErrorAction SilentlyContinue
    if ($c -and $c.ExecutablePath -and (Split-Path $c.ExecutablePath -Leaf) -eq "unity.exe" -and (Split-Path (Split-Path $c.ExecutablePath -Parent) -Leaf) -eq "resources" -and $c.CommandLine -match '(^|[\s"])serve([\s"]|$)') { $notes += "ignored: Unity Hub's helper (PID $($u.Id))" }
    else { $blockers += "a Unity Editor is running (PID $($u.Id)): close it first" }
}
if (-not (Test-Path $UnityExe)) { $blockers += "Unity editor not found at $UnityExe (give -UnityExe)" }
if (-not (Test-Path $py)) { $blockers += "the project venv python is missing: $py" }
$branch = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
$dirty = @(git -C $repo status --porcelain --untracked-files=no)
if ($dirty.Count) { $blockers += "a clean tracked tree is needed (the session records its git commit): $($dirty -join '; ')" }
if (Test-Path (Join-Path $rv "configs\trials.local.json")) { $blockers += "robot_vision\configs\trials.local.json exists (development override)" }
if ($timeout -ne [int]$finalPlan.timeout_s) { $blockers += "S1 timeout $timeout s differs from final_plan.json timeout_s $($finalPlan.timeout_s)" }
if ([int]$finalPlan.final_seed -ne 2) { $blockers += "final_plan.json final_seed is $($finalPlan.final_seed), S1 runs seed 2" }
if (-not $All -and -not $Plan -and $cells.Count -ne 1) { $blockers += "internal: one cell expected" }

# the state of every cell from its markers (S1_CELL_STARTED / _DONE / _INVALID in the s1_* session folders)
function CellState($character, $setting) {
    $parts = @()
    foreach ($d in @(Get-ChildItem $outputs -Directory -Filter ($s1.folder_prefix + "*") -ErrorAction SilentlyContinue)) {
        $m = Join-Path $d.FullName $s1.marker_started
        if (-not (Test-Path $m)) { continue }
        if (Test-Path (Join-Path $d.FullName "NOT_STARTED.txt")) { continue }     # refused before run 1: no run began, not a start
        $j = Json $m
        if ($j.character -eq $character -and $j.s1_setting -eq $setting) {
            $parts += [pscustomobject]@{ Folder = $d.Name; Part = [int]$j.part; Done = (Test-Path (Join-Path $d.FullName $s1.marker_done)); Invalid = (Test-Path (Join-Path $d.FullName $s1.marker_invalid)) }
        }
    }
    $parts
}
$todo = @()
foreach ($c in $cells) {
    $p = @(CellState $c.Character $c.Setting)
    $fx = Json (Join-Path $assets "Avatar\Config\sessions\final_ab_$($c.Setting).json")
    if (-not (Test-Path (Join-Path $rv $fx.python_control))) { $blockers += "$($c.Character)/$($c.Setting): the control file $($fx.python_control) does not exist" }
    if ($c.Setting -eq "B3" -and $fx.lie_detection -ne "on") { $blockers += "B3 must run with lie handling on, its config says '$($fx.lie_detection)'" }
    $c | Add-Member -NotePropertyName Control -NotePropertyValue $fx.python_control -Force
    if (@($p | Where-Object { $_.Invalid }).Count) { $notes += "cell $($c.Character)/$($c.Setting): INVALID (second interruption), never rerun"; continue }
    if (@($p | Where-Object { $_.Done }).Count) { $notes += "cell $($c.Character)/$($c.Setting): already finished ($(@($p | ForEach-Object Folder) -join ', ')), skipped"; continue }
    if ($p.Count -ge 2) { $blockers += "cell $($c.Character)/$($c.Setting) was interrupted twice: INVALID, no third part"; continue }
    if ($p.Count -eq 1 -and -not $Resume) { $blockers += "cell $($c.Character)/$($c.Setting) was started ($($p[0].Folder)) and has no end: if the Editor, the server or the machine died, resume it ONCE: run_s1.ps1 -Character $($c.Character) -Setting $($c.Setting) -Resume"; continue }
    if ($p.Count -eq 0 -and $Resume) { $blockers += "-Resume: cell $($c.Character)/$($c.Setting) has no earlier session"; continue }
    $c | Add-Member -NotePropertyName Resume -NotePropertyValue ($p.Count -eq 1) -Force
    $todo += $c
}
Say "S1 (post-freeze, exploratory; $($s1.amendment)): $(@($todo).Count) cell(s) to run of $($cells.Count), $runsPerCell runs each, seed $($finalPlan.final_seed), timeout $timeout s, Unity $unityVersion in the Editor window, branch $branch$(if ($DryRun) { ' (DRY RUN: nothing is run)' })"
foreach ($n in $notes) { Say "    note: $n" }
$k = 0
foreach ($c in $todo) {
    $k++
    $cellPlanRuns = @($s1.settings | Where-Object { $_.name -eq $c.Setting })[0].plan_runs
    Say "    cell $k`: $($c.Character) / $($c.Setting)  plan runs $(@($cellPlanRuns) -join ', ')  control $($c.Control)$(if ($c.Resume) { '  RESUME (once)' })"
}
if ($blockers.Count) {
    Say "    $(if ($DryRun) { 'a real run would be REFUSED now' } else { 'REFUSED' }):"
    foreach ($b in $blockers) { Say "      - $b" }
    if (-not $DryRun) { exit 1 }
}
if (@($todo).Count -eq 0) { Say "nothing to run."; exit 0 }
if ($DryRun) {
    foreach ($c in $todo) {
        $label = "s1_$($c.Character)_$($c.Setting)"
        Say ""
        Say "[$label] run_protocol_v4.ps1 -Label $label; cd robot_vision; $py launch_prep.py --task $($finalPlan.task)"
        Say "[$label] server: $py -u -m bridge.server --mode guide --task $($finalPlan.task) --perception vision --config configs/v4/bridge.json --control-config $($c.Control) --resource-log --exit-on-disconnect"
        Say "[$label] Unity: $(Q $UnityExe) -projectPath $(Q $project) -executeMethod WarehouseRobot.ScenarioEditor.TrialPlayV4.Run -s1Character $($c.Character) -s1Setting $($c.Setting)$(if ($c.Resume) { ' -s1Resume' }) -trialTimeout $($runsPerCell * $timeout + 1800) -logFile <log>"
        Say "[$label] check: finals_v4\check_s1_session.ps1 -U <session> -B <bridge> -Character $($c.Character) -Setting $($c.Setting)"
    }
    Say ""; Say "DRY RUN: nothing was run."; exit 0
}

# ---- run the cells
$manifestFile = Join-Path $outputs "s1_runs.json"
function AddManifest($entry) {
    $list = @()
    if (Test-Path $manifestFile) { $list = @((Get-Content $manifestFile -Raw | ConvertFrom-Json)) }
    $list += $entry
    $json = ConvertTo-Json -InputObject @($list) -Depth 6
    [System.IO.File]::WriteAllText($manifestFile, $json + "`n", (New-Object System.Text.UTF8Encoding $false))
}

$script:cellStatus = 1
function RunCell($c) {
    $character = $c.Character; $setting = $c.Setting; $resume = [bool]$c.Resume
    $label = "s1_${character}_${setting}"
    $cstamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $transcript = Join-Path $outputs "run_s1_${label}_${cstamp}_transcript.log"
    $crashFile = Join-Path $outputs "run_s1_${label}_${cstamp}_crashwatch.log"
    $serverOut = Join-Path $outputs "run_s1_${label}_${cstamp}_server.log"
    $serverErr = Join-Path $outputs "run_s1_${label}_${cstamp}_server.err.log"
    $unityLog = Join-Path $outputs "run_s1_${label}_${cstamp}_unity.log"
    foreach ($f in $transcript, $crashFile, $serverOut, $serverErr, $unityLog) { if (Test-Path $f) { Say "STOPPED: $f exists; not overwritten"; $script:cellStatus = 1; return } }
    Start-Transcript -Path $transcript | Out-Null
    $server = $null; $unity = $null; $status = 1; $bridge = ""; $session = ""; $note = ""; $crash = @()
    try {
        Say ""; Say "=== S1 cell $character / $setting$(if ($resume) { ' (RESUME)' }) ==="
        $noteOut = @(& (Join-Path $PSScriptRoot "run_protocol_v4.ps1") -Label $label)
        $noteOut | Select-Object -SkipLast 1 | ForEach-Object { Say $_ }
        $note = [string]$noteOut[-1]
        if (-not (Test-Path $note)) { throw "the protocol note was not written" }
        Push-Location $rv
        try { & $py launch_prep.py --task $finalPlan.task | ForEach-Object { Say "    $_" }; if ($LASTEXITCODE -ne 0) { throw "launch_prep refused" } } finally { Pop-Location }
        $serverArgs = @("-u", "-m", "bridge.server", "--mode", "guide", "--task", $finalPlan.task, "--perception", "vision", "--config", "configs/v4/bridge.json",
                        "--control-config", $c.Control, "--resource-log", "--exit-on-disconnect")
        $env:PYTHONIOENCODING = "utf-8"
        $server = Start-Process -FilePath $py -ArgumentList $serverArgs -WorkingDirectory $rv -NoNewWindow -PassThru -RedirectStandardOutput $serverOut -RedirectStandardError $serverErr
        $null = $server.Handle
        $deadline = (Get-Date).AddSeconds(900)
        while ($true) {
            $line = Select-String -Path $serverOut -Pattern "listening on .*; run folder (.+)$" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($line) { $bridge = $line.Matches[0].Groups[1].Value.Trim(); break }
            if ($server.HasExited) { Get-Content $serverOut, $serverErr -Tail 15 -ErrorAction SilentlyContinue | ForEach-Object { Say "    $_" }; throw "the server exited before listening (nothing was run)" }
            if ((Get-Date) -gt $deadline) { throw "the server did not say listening within 900 s (PID $($server.Id) left running)" }
            Start-Sleep -Seconds 1
        }
        Say "    server listening; bridge run folder $bridge"
        $unityArgs = @("-projectPath", (Q $project), "-executeMethod", "WarehouseRobot.ScenarioEditor.TrialPlayV4.Run", "-s1Character", $character, "-s1Setting", $setting) +
                     $(if ($resume) { @("-s1Resume") } else { @() }) + @("-trialTimeout", ($runsPerCell * $timeout + 1800), "-logFile", (Q $unityLog))
        $started = Get-Date
        $unity = Start-Process -FilePath $UnityExe -ArgumentList $unityArgs -PassThru
        $null = $unity.Handle
        Say "    Unity started (PID $($unity.Id)): $(Q $UnityExe) $($unityArgs -join ' ')"
        # the crash watch: Unity quits by itself when the cell is done; the server dying first is an infrastructure interruption
        $serverDied = $false
        while (-not $unity.WaitForExit(2000)) {
            if ($server.HasExited) { $serverDied = $true; $crash += "$(Get-Date -Format s) the bridge server (PID $($server.Id)) exited with code $($server.ExitCode) while Unity was running"; Stop-Process -Id $unity.Id -Force -ErrorAction SilentlyContinue; $null = $unity.WaitForExit(30000); break }
        }
        $finished = Select-String -Path $unityLog -Pattern "\[TrialPlayV4\] finished" -ErrorAction SilentlyContinue | Select-Object -Last 1
        Say "    Unity exit code $($unity.ExitCode): $(if ($finished) { $finished.Line.Trim() } else { 'no [TrialPlayV4] finished line in ' + $unityLog })"
        $refused = Select-String -Path $unityLog -Pattern "S1 refused:|not started:" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($refused) { Say "    $($refused.Line.Trim())" }
        if (-not $serverDied -and -not $finished) { $crash += "$(Get-Date -Format s) Unity (PID $($unity.Id)) ended with exit code $($unity.ExitCode) and no [TrialPlayV4] finished line" }
        if (-not $server.WaitForExit(300000)) { $crash += "$(Get-Date -Format s) the server (PID $($server.Id)) did not exit within 300 s after Unity quit"; throw "the server did not exit after Unity quit; stop it by hand (summary.json is written on a clean stop)" }
        Say "    server exited ($(if (Test-Path (Join-Path $bridge 'summary.json')) { 'summary.json written' } else { 'NO summary.json' }))"
        # Event Viewer: application errors of Unity or python since the start
        try {
            $ev = @(Get-WinEvent -FilterHashtable @{ LogName = "Application"; Id = 1000, 1001; StartTime = $started } -ErrorAction Stop | Where-Object { $_.Message -match "Unity\.exe|python\.exe" })
            foreach ($e in $ev) { $crash += "$($e.TimeCreated.ToString('s')) Event $($e.Id): $((($e.Message -split "`n")[0..2] -join ' ').Trim())" }
        } catch { if ($_.Exception.Message -notmatch "No events were found") { $crash += "Event Viewer could not be read: $($_.Exception.Message)" } }
        $found = @(Get-ChildItem $outputs -Directory -Filter "$($s1.folder_prefix)${character}_${setting}_*" | Where-Object { $_.CreationTime -ge $started.AddSeconds(-5) })
        if ($found.Count -ne 1) { throw "expected one new $($s1.folder_prefix)${character}_${setting}_* folder, found $($found.Count)" }
        $session = $found[0].FullName
        $startRun = 1
        $sj = Json (Join-Path $session "session.json")
        if ($sj) { $startRun = [int]$sj.start_run }
        $out = @(& (Join-Path $PSScriptRoot "check_s1_session.ps1") -U $session -B $bridge -Character $character -Setting $setting -StartRun $startRun -Protocol $note)
        $valid = ($LASTEXITCODE -eq 0)
        $out | ForEach-Object { Say "    $_" }
        Say ""
        Say "Unity session: $session"
        Say "bridge run:    $bridge"
        Say "protocol note: $note"
        Say "logs:          $serverOut, $unityLog"
        if ($crash.Count) { Say "CRASH WATCH: $($crash.Count) entr$(if ($crash.Count -eq 1) { 'y' } else { 'ies' }) (see $crashFile)" }
        $status = $(if ($valid) { 0 } else { 1 })
        AddManifest ([pscustomobject]@{ character = $character; setting = $setting; part = $(if ($resume) { 2 } else { 1 }); unity_session = (Split-Path $session -Leaf); bridge_run = (Split-Path $bridge -Leaf);
                                       protocol_note = (Split-Path $note -Leaf); transcript = (Split-Path $transcript -Leaf); crashwatch = (Split-Path $crashFile -Leaf); server_log = (Split-Path $serverOut -Leaf);
                                       server_err_log = (Split-Path $serverErr -Leaf); unity_log = (Split-Path $unityLog -Leaf); valid = $valid; time = (Get-Date -Format s) })
        Say $(if ($valid) { "S1 CELL $character/$setting RECORDED (valid)." } else { "S1 CELL $character/$setting INVALID: reported as it stands, never rerun." })
    } catch {
        Say "STOPPED: $($_.Exception.Message)"
        $crash += "$(Get-Date -Format s) STOPPED: $($_.Exception.Message)"
        Say "If the Editor, the server or the machine died before a run finished, resume this cell ONCE: finals_v4\run_s1.ps1 -Character $character -Setting $setting -Resume"
        $status = 1
    } finally {
        if ($unity -and -not $unity.HasExited) { Say "    Unity (PID $($unity.Id)) is still running: close it by hand" }
        if ($server -and -not $server.HasExited) { Say "    the server (PID $($server.Id)) is still running: stop it by hand (Ctrl+C in its window or Stop-Process)" }
        $lines = @("S1 crash watch of $label, $cstamp", "unity exit code: $(if ($unity -and $unity.HasExited) { $unity.ExitCode } else { 'n/a' })", "server exit code: $(if ($server -and $server.HasExited) { $server.ExitCode } else { 'n/a' })") + $(if ($crash.Count) { $crash } else { "no entry" })
        [System.IO.File]::WriteAllLines($crashFile, $lines)
        Stop-Transcript | Out-Null
    }
    $script:cellStatus = $status
}

$overall = 0
foreach ($c in $todo) {
    RunCell $c
    if ($script:cellStatus -ne 0) { $overall = 1; Say "Stopping after the failed cell $($c.Character)/$($c.Setting); the cells after it were not started."; break }
}
exit $overall
