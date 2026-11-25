param(
    [string]$OutputsRoot = "",     # default: the outputs folder of robot_vision\configs\trials.json
    [switch]$Csv                   # also write robot_vision\outputs\s1_summary_<time>.csv (a new file, never overwritten)
)
# A quick DESCRIPTIVE summary of the S1 sessions from Unity's result files only (results_unity.csv and session.json of every s1_* session folder):
# successes out of runs per character x setting, and one row per run (plan run, goal, outcome, failure reason). No Python result file, no Wilson interval, no
# comparison with the finals, no inference: Anisha's process_supplementary_zip_v4.py makes the evaluation. A resumed cell (two parts) is one cell:
# the runs of both parts are counted once, and the interrupted run (which has no outcome) is not listed.
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$rv = Join-Path $repo "robot_vision"
$trials = Get-Content (Join-Path $rv "configs\trials.json") -Raw | ConvertFrom-Json
$outputs = if ($OutputsRoot) { $OutputsRoot } else { Join-Path $rv $trials.output_root }
$rows = @()
foreach ($d in @(Get-ChildItem $outputs -Directory -Filter "s1_*" -ErrorAction SilentlyContinue | Sort-Object Name)) {
    $sj = Join-Path $d.FullName "session.json"
    $res = Join-Path $d.FullName "results_unity.csv"
    if (-not (Test-Path $sj) -or -not (Test-Path $res)) { Write-Host "skipped (no session.json or results_unity.csv yet): $($d.Name)"; continue }
    $s = Get-Content $sj -Raw | ConvertFrom-Json
    if ($s.supplementary -ne "S1") { continue }
    foreach ($r in @(Import-Csv $res)) {
        $trial = [int]$r.trial
        $rows += [pscustomobject]@{
            character = $s.s1_character; setting = $s.s1_setting; part = [int]$s.s1_part; session = $d.Name; run = $trial; plan_run = @($s.plan_runs)[$trial - 1]
            goal = $r.b_name; outcome = $r.outcome; failure_reason = $r.failure_reason; total_s = $r.total_s; collisions = $r.collisions
        }
    }
}
if ($rows.Count -eq 0) { Write-Host "no S1 result found in $outputs"; exit 0 }
Write-Host "S1 (post-freeze, exploratory; descriptive only, from Unity's result files): successes / runs per character x setting"
$cells = $rows | Group-Object character, setting
$table = foreach ($g in ($cells | Sort-Object { $_.Group[0].character }, { $_.Group[0].setting })) {
    $runs = @($g.Group | Sort-Object plan_run -Unique)
    $ok = @($runs | Where-Object { $_.outcome -eq "SUCCESS" }).Count
    [pscustomobject]@{ character = $g.Group[0].character; setting = $g.Group[0].setting; successes = $ok; runs = $runs.Count; of = 5
                       failed = (@($runs | Where-Object { $_.outcome -ne "SUCCESS" } | ForEach-Object { "run $($_.plan_run): $($_.failure_reason)" }) -join "; ") }
}
$table | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
Write-Host "per run:"
$rows | Sort-Object character, setting, run | Format-Table character, setting, part, run, plan_run, goal, outcome, failure_reason, total_s, collisions -AutoSize | Out-String -Width 200 | Write-Host
if ($Csv) {
    $file = Join-Path $outputs ("s1_summary_{0:yyyyMMdd_HHmmss}.csv" -f (Get-Date))
    if (Test-Path $file) { Write-Host "REFUSED: $file exists"; exit 2 }
    $rows | Export-Csv -Path $file -NoTypeInformation -Encoding UTF8
    Write-Host "written: $file"
}
