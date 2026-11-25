param(
    [Parameter(Mandatory = $true)][string]$U,         # the S1 Unity session folder, e.g. robot_vision\outputs\s1_anime_f_01_A1_<time>
    [Parameter(Mandatory = $true)][string]$B,         # its bridge run folder, e.g. robot_vision\outputs\bridge_guide_<time>
    [Parameter(Mandatory = $true)][string]$Character, # one of the four S1 characters
    [Parameter(Mandatory = $true)][string]$Setting,   # A1, A3 or B3
    [int]$StartRun = 1,                               # 2nd part of a resumed cell: runs k..5
    [string]$Protocol = ""                            # the pre-session run-protocol note
)
# The validity check of ONE S1 cell session (post-freeze supplementary experiment S1; Unity addendum 14 of Avatar/Config/experiments_ab.md).
# Validity only, no performance threshold; a watchdog stop is a result, not a reason for invalidity. It is the S1 counterpart of
# check_session_v4.ps1 (B11), which cannot be used as it is: its split guard (criterion 3) refuses the four avatar-experiment looks by design, and S1
# needs no frozen match. Here: the leak test; the S1 split guard (data_splits_v4.guard_run(supplementary="S1"): ONE look, one of the four, listed
# test clips); session.json (supplementary, seed 2, timeout 480, setting, character, plan_runs as declared); the runs present; every truth and run file
# accepted by Anisha's checkers; no final run-once marker anywhere (by exact name, addendum 14 amendment 3); the run protocol recorded. Read-only (gt_path.py session writes leak_test/leak_test.json
# by design, as for the finals). Exit 0 = every criterion PASS.
$ErrorActionPreference = "Continue"
$repo = Split-Path $PSScriptRoot -Parent
$rv = Join-Path $repo "robot_vision"
$py = Join-Path $rv ".venv\Scripts\python.exe"
function Full($p) { if ([System.IO.Path]::IsPathRooted($p)) { $p } else { [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $p)) } }
$U = Full $U
$B = Full $B
if ($Protocol) { $Protocol = Full $Protocol }
$cfg = Get-Content (Join-Path $repo "unity\Robotics-Warehouse\WarehouseProjectURP\Assets\WarehouseRobot\Avatar\Config\s1_supplementary.json") -Raw | ConvertFrom-Json
$def = @($cfg.settings | Where-Object { $_.name -eq $Setting })
if ($def.Count -ne 1 -or @($cfg.characters) -notcontains $Character) { "REFUSED: $Character / $Setting is not an S1 cell"; exit 2 }
$runs = [int]$cfg.runs_per_cell
if ($StartRun -lt 1 -or $StartRun -gt $runs) { "REFUSED: -StartRun $StartRun is outside 1..$runs"; exit 2 }
$fail = 0
function Report($n, $ok, $what) { if ($ok) { "PASS $n $what" } else { "FAIL $n $what"; $script:fail++ } }
function ReadJson($path) { if (Test-Path $path) { Get-Content $path -Raw | ConvertFrom-Json } else { $null } }
function Numbers($names, $pattern) { @($names | ForEach-Object { if ($_ -match $pattern) { [int]$Matches[1] } } | Sort-Object) }
"S1 cell $Character / $Setting (plan runs $(@($def[0].plan_runs) -join ', ')), runs $StartRun..$runs"
"session: $U"
"bridge:  $B"
Push-Location $rv
try {
    $s = ReadJson (Join-Path $U "session.json")
    $sum = ReadJson (Join-Path $B "summary.json")
    $runDirs = @(Get-ChildItem $U -Directory -Filter "run_*" -ErrorAction SilentlyContinue)

    $null = & $py gt_path.py session $U 2>&1; $leakPy = ($LASTEXITCODE -eq 0)
    $leakU = ($null -ne $s) -and ($s.leak_test.passed -eq $true)
    Report 1 ($leakU -and $leakPy) "leak test passed: Unity $leakU, Python (gt_path.py session) $leakPy"

    $why = @()
    if ($null -eq $s) { $why += "no session.json" }
    else {
        if ($s.supplementary -ne "S1") { $why += "supplementary '$($s.supplementary)'" }
        if ($s.seed -ne 2) { $why += "seed $($s.seed)" }
        if ([float]$s.timeout_s -ne [float]$cfg.timeout_s) { $why += "timeout $($s.timeout_s) s" }
        if ($s.final_setting -ne $Setting -or $s.s1_setting -ne $Setting) { $why += "setting '$($s.final_setting)' / '$($s.s1_setting)'" }
        if ($s.s1_character -ne $Character) { $why += "character '$($s.s1_character)'" }
        if ((@($s.plan_runs) -join ",") -ne (@($def[0].plan_runs) -join ",")) { $why += "plan_runs [$(@($s.plan_runs) -join ',')]" }
        if ($s.mode -eq "final") { $why += "mode final" }
        if ([int]$s.start_run -ne $StartRun) { $why += "start_run $($s.start_run)" }
        if ($StartRun -gt 1 -and $s.s1_part -ne 2) { $why += "s1_part $($s.s1_part) in a resumed session" }
    }
    Report 2 ($why.Count -eq 0) "session.json: supplementary S1, seed 2, timeout $($cfg.timeout_s) s, setting, character, plan_runs as declared$(if ($why.Count) { ': ' + ($why -join '; ') })"

    $splitCode = @'
import sys, gesture_data as gd, data_splits_v4 as ds
from pathlib import Path
character = sys.argv[2]
runs = sorted(Path(sys.argv[1]).glob('run_[0-9][0-9][0-9]'))
bad = [] if runs else ['no run folder']
for r in runs:
    try:
        t = gd.load_truth(r / 'truth.jsonl')
        looks = {x.look for x in t}
        ds.guard_run(looks, {c.clip for c in gd.build_clips(t)}, final_evaluation=False, supplementary='S1')
        if looks != {character}:
            bad.append(r.name + ': looks ' + str(sorted(looks)) + ', expected only ' + character)
    except (SystemExit, ValueError, OSError) as e:
        bad.append(r.name + ': ' + str(e))
print(' | '.join(bad) if bad else f'{len(runs)} runs, every run wholly in {character}, test clips')
sys.exit(1 if bad else 0)
'@
    $splitOut = (& $py -c $splitCode $U $Character 2>&1) -join " "
    Report 3 ($LASTEXITCODE -eq 0) "S1 split guard (data_splits_v4.guard_run, supplementary S1): $splitOut"

    $want = @($StartRun..$runs)
    $rows = @(Import-Csv (Join-Path $U "results_unity.csv") -ErrorAction SilentlyContinue)
    $rowNums = @($rows | ForEach-Object { [int]$_.trial } | Sort-Object)
    $dirNums = Numbers ($runDirs | ForEach-Object Name) '^run_(\d{3})$'
    $pyNums = Numbers (Get-ChildItem $B -File -Filter "python_trial_*.json" -ErrorAction SilentlyContinue | ForEach-Object Name) '^python_trial_(\d{3})\.json$'
    $same = { param($a) ($a -join ",") -eq ($want -join ",") }
    Report 4 ((& $same $rowNums) -and (& $same $dirNums) -and (& $same $pyNums)) "all runs present: results_unity.csv trials [$($rowNums -join ',')], run_### [$($dirNums -join ',')], python_trial_### [$($pyNums -join ',')]; expected $StartRun..$runs"

    # addendum 14 amendment 3: the final run-once markers by their EXACT names (case-sensitive): Python's FINAL_MARKERS (process_supplementary_zip_v4.py)
    # and Unity's done file (final_v4.json done_file). Until then a FINAL* wildcard filter (case-insensitive on Windows) also counted config_used\final_ab_<setting>.json,
    # final_plan.json and final_v4.json, the byte copies of the finals' configs that every S1 (and final) session keeps as its inputs: not markers.
    $finalMarkers = @("FINAL_DONE.json", "FINAL_EXPORT_DONE.json", "FINAL_RUN_DONE.json", "FINAL_SETTING.json", "FINAL_INTERRUPTION.json", "FINAL_RESUME.json",
                      "FINAL_INVALID.json", "FINAL_EVAL_SUPERSEDED.json")
    $finalMarkers += [string](Get-Content (Join-Path $repo "unity\Robotics-Warehouse\WarehouseProjectURP\Assets\WarehouseRobot\Avatar\Config\final_v4.json") -Raw | ConvertFrom-Json).done_file
    $markerFiles = @(Get-ChildItem $U, $B -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $finalMarkers -ccontains $_.Name })
    $configCopies = @(Get-ChildItem (Join-Path $U "config_used"), (Join-Path $B "config_used") -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "final*" })
    $have = (Test-Path (Join-Path $U "summary_unity.json")) -and ($null -ne $sum) -and (Test-Path (Join-Path $U $cfg.marker_done))
    Report 5 ($have -and $markerFiles.Count -eq 0) "every outcome recorded (summary_unity.json, summary.json, $($cfg.marker_done)): $have; final run-once markers ($($finalMarkers -join ', ')): $($markerFiles.Count)$(if ($markerFiles.Count) { ' (' + (($markerFiles | ForEach-Object FullName) -join ', ') + ')' }); config_used copies of the finals' configs (inputs, not markers): $(@($configCopies | ForEach-Object Name) -join ', ')"

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
    "RESULT (not a validity criterion): watchdog stops reported by Unity: $stops"
} finally { Pop-Location }
if ($fail) { "S1 CELL INVALID: $fail criterion/criteria failed. Report it with these reasons; a cell is never rerun (an infrastructure interruption may be resumed once)." }
else { "S1 CELL VALID: every criterion passed" }
exit $fail
