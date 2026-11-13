param(
    [Parameter(Mandatory = $true)][string]$U,      # Unity session folder, e.g. outputs\trials_final_Task2_zoom_on_<time>
    [Parameter(Mandatory = $true)][string]$B,      # bridge run folder, e.g. outputs\bridge_guide_<time>
    [int]$Runs = 0,                                # runs expected; a final: runs_per_setting of final_plan.json (another number is refused)
    [switch]$Final,                                # a final: frozen hashes, the test split and the run-once markers are required
    [string]$Protocol = ""                         # the pre-session run-protocol note (free memory, programs running)
)
# The B11 validity criteria of a v4 session (final_plan.json acceptance_criteria; adopted 2026-11-13, confirmed by Anisha and
# updated the same day: AUDIT.md section 15). Validity only, no performance threshold. A watchdog stop is a RESULT (a stop, or the
# failure, of its run), never a reason for invalidity: it is printed, not checked. Read-only; works from any folder (relative
# paths are taken from the current folder). Exit 0 = every criterion PASS (the session is valid); 2 = refused (wrong arguments).
$rv = Join-Path (Split-Path $PSScriptRoot -Parent) "robot_vision"
$py = Join-Path $rv ".venv\Scripts\python.exe"
function Full($p) { if ([System.IO.Path]::IsPathRooted($p)) { $p } else { [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $p)) } }
$U = Full $U
$B = Full $B
if ($Protocol) { $Protocol = Full $Protocol }
$plan = Get-Content (Join-Path $rv "configs\v4\final_plan.json") -Raw | ConvertFrom-Json
if ($Final) {
    if ($Runs -eq 0) { $Runs = [int]$plan.runs_per_setting }
    if ($Runs -ne [int]$plan.runs_per_setting) { "REFUSED: a final has runs_per_setting = $($plan.runs_per_setting) runs (final_plan.json), not $Runs"; exit 2 }
} elseif ($Runs -lt 1) { "REFUSED: give -Runs (the runs of this development session)"; exit 2 }
$fail = 0
# $ok: $true PASS, $false FAIL (counted), $null N/A (development only; not counted)
function Report($n, $ok, $what) {
    if ($null -eq $ok) { "N/A  $n $what" } elseif ($ok) { "PASS $n $what" } else { "FAIL $n $what"; $script:fail++ }
}
function ReadJson($path) { if (Test-Path $path) { Get-Content $path -Raw | ConvertFrom-Json } else { $null } }
function Numbers($names, $pattern) { @($names | ForEach-Object { if ($_ -match $pattern) { [int]$Matches[1] } } | Sort-Object) }
"session: $U"
"bridge:  $B"
"$(if ($Final) { 'FINAL' } else { 'development' }), $Runs runs expected"
Push-Location $rv
try {
    $s = ReadJson (Join-Path $U "session.json")
    $sum = ReadJson (Join-Path $B "summary.json")
    $runDirs = @(Get-ChildItem $U -Directory -Filter "run_*" -ErrorAction SilentlyContinue)

    $null = & $py gt_path.py session $U 2>&1; $leakPy = ($LASTEXITCODE -eq 0)
    $leakU = ($null -ne $s) -and ($s.leak_test.passed -eq $true)
    Report 1 ($leakU -and $leakPy) "leak test passed: Unity $leakU, Python (gt_path.py session) $leakPy"

    $frozenOut = (& $py -c "import freeze_v4 as fz; fz.require_frozen(); print('frozen, every hash matches')" 2>&1) -join " "
    $frozenOk = ($LASTEXITCODE -eq 0)
    Report 2 $(if ($Final) { $frozenOk } else { $null }) "frozen hashes match: $frozenOut$(if (-not $Final) { ' (development: not required)' })"

    $splitCode = @'
import sys, gesture_data as gd, data_splits_v4 as ds
from pathlib import Path
final = sys.argv[2] == '1'
runs = sorted(Path(sys.argv[1]).glob('run_[0-9][0-9][0-9]'))
bad = [] if runs else ['no run folder']
for r in runs:
    try:
        t = gd.load_truth(r / 'truth.jsonl')
        split = ds.guard_run({x.look for x in t}, {c.clip for c in gd.build_clips(t)}, final_evaluation=final)
    except (SystemExit, ValueError, OSError) as e:
        bad.append(r.name + ': ' + str(e))
print(' | '.join(bad) if bad else f'{len(runs)} runs, every run wholly in the ' + ('test' if final else 'development') + ' split')
sys.exit(1 if bad else 0)
'@
    $splitOut = (& $py -c $splitCode $U $(if ($Final) { "1" } else { "0" }) 2>&1) -join " "
    $splitOk = ($LASTEXITCODE -eq 0)
    Report 3 $splitOk "split guard passed (data_splits_v4.guard_run, final_evaluation $([bool]$Final)): $splitOut"

    $want = @(1..$Runs)
    $rows = @(Import-Csv (Join-Path $U "results_unity.csv") -ErrorAction SilentlyContinue)
    $rowNums = @($rows | ForEach-Object { [int]$_.trial } | Sort-Object)
    $dirNums = Numbers ($runDirs | ForEach-Object Name) '^run_(\d{3})$'
    $pyNums = Numbers (Get-ChildItem $B -File -Filter "python_trial_*.json" -ErrorAction SilentlyContinue | ForEach-Object Name) '^python_trial_(\d{3})\.json$'
    $same = { param($a) ($a -join ",") -eq ($want -join ",") }
    $allRuns = (& $same $rowNums) -and (& $same $dirNums) -and (& $same $pyNums)
    Report 4 $allRuns "all runs present: results_unity.csv trials [$($rowNums -join ',')], run_### [$($dirNums -join ',')], python_trial_### [$($pyNums -join ',')]; expected 1..$Runs"

    $have = (Test-Path (Join-Path $U "summary_unity.json")) -and ($null -ne $sum)
    $markers = (Test-Path (Join-Path $U "UNITY_FINAL_DONE.json")) -and (Test-Path (Join-Path $B "FINAL_RUN_DONE.json"))
    Report 5 ($have -and ($markers -or -not $Final)) "every outcome recorded: summary_unity.json and summary.json $have; final markers $(if ($Final) { $markers } else { 'n/a (development)' })"

    $bad = @()
    foreach ($r in $runDirs) {
        $null = & $py gesture_data.py (Join-Path $r.FullName "truth.jsonl") 2>&1; if ($LASTEXITCODE -ne 0) { $bad += "$($r.Name) truth" }
        $null = & $py gt_path.py run $r.FullName 2>&1; if ($LASTEXITCODE -ne 0) { $bad += "$($r.Name) run files" }
    }
    Report 6 ($runDirs.Count -gt 0 -and $bad.Count -eq 0) "every truth and run file accepted: $(if ($bad.Count) { $bad -join ', ' } elseif ($runDirs.Count) { 'all accepted' } else { 'no run folder' })"

    $info = ReadJson (Join-Path $B "run_info.json")
    $machine = if ($info) { @($info.PSObject.Properties.Name | Where-Object { $_ -match "machine" }) } else { @() }
    $resources = Test-Path (Join-Path $B "resources.csv")
    $note = [bool]($Protocol -and (Test-Path $Protocol) -and (Select-String -Path $Protocol -Pattern "free memory" -Quiet))
    Report 7 ($machine.Count -gt 0 -and $resources -and $note) "run protocol recorded: run_info.json $($machine -join ',') $($machine.Count -gt 0), resources.csv $resources, pre-session note $(if ($Protocol) { $Protocol } else { 'not given' }) $note"

    $stops = if ($sum) { $sum.watchdog.stops_reported_by_unity } else { "unknown (no summary.json)" }
    "RESULT (not a validity criterion): watchdog stops reported by Unity: $stops; each one counts as a stop of its run, or as its failure if the run failed"
} finally { Pop-Location }

if ($fail) {
    if ($Final) { "SESSION INVALID: $fail criterion/criteria failed. Report this setting as invalid with the reasons above; it is never rerun." }
    else { "SESSION INVALID (development): $fail criterion/criteria failed" }
} else { "SESSION VALID: every criterion passed" }
exit $fail
