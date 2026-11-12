param(
    [Parameter(Mandatory = $true)][string]$U,      # Unity session folder, e.g. outputs\trials_final_Task2_zoom_on_<time>
    [Parameter(Mandatory = $true)][string]$B,      # bridge run folder, e.g. outputs\bridge_guide_<time>
    [Parameter(Mandatory = $true)][int]$Runs,      # runs expected (20 in a final)
    [switch]$Final,                                # a final: the run-once markers must exist too
    [string]$Protocol = ""                         # the pre-session run-protocol note (free memory, programs running)
)
# The five B11 validity criteria of a v4 session (final_plan.json acceptance_criteria, adopted 2026-11-13; AUDIT.md section 15).
# Run from robot_vision\. -Protocol is the note written by finals_v4\run_protocol_v4.ps1 before the session. Read-only.
# Exit 0 = all five PASS (the session is valid).
$py = ".\.venv\Scripts\python.exe"
$fail = 0
function Report($n, $ok, $what) { if ($ok) { "PASS $n $what" } else { "FAIL $n $what"; $script:fail++ } }

# 1. leak test, Unity and Python
$s = Get-Content (Join-Path $U "session.json") -Raw | ConvertFrom-Json
& $py gt_path.py session $U *> $null; $leakPy = ($LASTEXITCODE -eq 0)
Report 1 ($s.leak_test.passed -eq $true -and $leakPy) "leak test: Unity $($s.leak_test.passed), Python $leakPy"

# 2. every outcome recorded
$rows = @(Import-Csv (Join-Path $U "results_unity.csv")).Count
$runDirs = @(Get-ChildItem $U -Directory -Filter "run_*").Count
$pyTrials = @(Get-ChildItem $B -File -Filter "python_trial_*.json").Count
$have = (Test-Path (Join-Path $U "summary_unity.json")) -and (Test-Path (Join-Path $B "summary.json"))
$markers = $true
if ($Final) { $markers = (Test-Path (Join-Path $U "UNITY_FINAL_DONE.json")) -and (Test-Path (Join-Path $B "FINAL_RUN_DONE.json")) }
Report 2 ($rows -eq $Runs -and $runDirs -eq $Runs -and $pyTrials -eq $Runs -and $have -and $markers) "outcomes: $rows rows, $runDirs run folders, $pyTrials python trials (expected $Runs); summaries $have; final markers $(if ($Final) { $markers } else { 'n/a (development)' })"

# 3. every truth and run file accepted
$bad = @()
foreach ($r in Get-ChildItem $U -Directory -Filter "run_*") {
    & $py gesture_data.py (Join-Path $r.FullName "truth.jsonl") *> $null; if ($LASTEXITCODE -ne 0) { $bad += "$($r.Name) truth" }
    & $py gt_path.py run $r.FullName *> $null; if ($LASTEXITCODE -ne 0) { $bad += "$($r.Name) run files" }
}
Report 3 ($bad.Count -eq 0) "truth and run files: $(if ($bad.Count) { $bad -join ', ' } else { 'all accepted' })"

# 4. no watchdog stop after start-up
$sum = Get-Content (Join-Path $B "summary.json") -Raw | ConvertFrom-Json
$stops = $sum.watchdog.stops_reported_by_unity
Report 4 ($stops -eq 0) "watchdog stops reported by Unity: $stops"

# 5. run protocol recorded
$info = Get-Content (Join-Path $B "run_info.json") -Raw | ConvertFrom-Json
$machine = $info.PSObject.Properties.Name | Where-Object { $_ -match "machine" }
$resources = Test-Path (Join-Path $B "resources.csv")
$note = $Protocol -and (Test-Path $Protocol) -and (Select-String -Path $Protocol -Pattern "free memory" -Quiet)
Report 5 ($machine -and $resources -and $note) "run protocol: run_info.json $($machine -join ',') $([bool]$machine), resources.csv $resources, pre-session note $(if ($Protocol) { $Protocol } else { 'not given' }) $note"

if ($fail) { "SESSION INVALID: $fail criterion/criteria failed" } else { "SESSION VALID: all five criteria passed" }
exit $fail
