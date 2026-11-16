param(
    [Parameter(Mandatory = $true)][string]$Setting,   # e.g. A1, B2_right_off
    [Parameter(Mandatory = $true)][string]$Launcher   # the launcher's console output (it names the Unity session and the bridge run)
)
# Step 5 (development runs of the final matrix, 2026-11-16): the checks after one rehearsal session that the launcher's B11 check
# does not make, then the session's entry in robot_vision\outputs\step5_sessions.json for finals_v4\step5_report.py.
#   1. every run_###/truth.jsonl through gesture_data.py WITH --messages of the bridge run (the launcher's check runs it without);
#   2. gt_path.py session (leak test, Python side; the launcher's check also runs it);
#   3. Anisha's CSV export in development mode: export_csv_v4.py --session UNITY BRIDGE (a new export_csv_v4_<time> folder).
# Read-only on the session folders (gt_path.py session writes leak_test/leak_test.json by design). Exit 0 = every check passed.
$ErrorActionPreference = "Stop"
$rv = Join-Path (Split-Path $PSScriptRoot -Parent) "robot_vision"
$py = Join-Path $rv ".venv\Scripts\python.exe"
$text = Get-Content $Launcher -Raw
# the summary lines, or (if the launcher stopped before them) its "bridge run folder" line and the [TrialPlayV4] finished line
$U = [regex]::Match($text, "Unity session: (.+)").Groups[1].Value.Trim()
if (-not $U) { $U = [regex]::Match($text, "\(([^()\r\n]*trials_development_[^()\r\n]+)\)").Groups[1].Value.Trim() }
$B = [regex]::Match($text, "bridge run:\s+(.+)").Groups[1].Value.Trim()
if (-not $B) { $B = [regex]::Match($text, "bridge run folder (\S+)").Groups[1].Value.Trim() }
# the transcript is made portable below (paths relative to the repository root), so a second call reads relative paths
$repoRoot = Split-Path $PSScriptRoot -Parent
foreach ($v in "U", "B") { $x = Get-Variable $v -ValueOnly; if ($x -and -not [System.IO.Path]::IsPathRooted($x)) { Set-Variable $v (Join-Path $repoRoot $x) } }
if (-not $U -or -not $B -or -not (Test-Path $U) -or -not (Test-Path $B)) { "REFUSED: session or bridge folder not found in $Launcher"; exit 2 }
$fail = 0
Push-Location $rv
try {
    $ErrorActionPreference = "Continue"
    $s = Get-Content (Join-Path $U "session.json") -Raw | ConvertFrom-Json
    "leak test: Unity session.json leak_test.passed = $($s.leak_test.passed)"
    if ($s.leak_test.passed -ne $true) { $fail++ }
    $out = & $py gt_path.py session $U 2>&1; $ok = ($LASTEXITCODE -eq 0); if (-not $ok) { $fail++ }
    "leak test: Python gt_path.py session exit $LASTEXITCODE ($(($out | Select-Object -Last 1)))"
    $runs = @(Get-ChildItem $U -Directory -Filter "run_*")
    $bad = @()
    foreach ($r in $runs) {
        $o = & $py gesture_data.py (Join-Path $r.FullName "truth.jsonl") --messages (Join-Path $B "messages.jsonl") 2>&1
        if ($LASTEXITCODE -ne 0) { $bad += "$($r.Name): $(($o | Select-Object -Last 1))" }
    }
    if ($bad.Count) { $fail++ }
    "truth: gesture_data.py --messages accepted $($runs.Count - $bad.Count) of $($runs.Count) runs$(if ($bad.Count) { ': ' + ($bad -join '; ') })"
    $before = @(Get-ChildItem (Join-Path $rv "outputs") -Directory -Filter "export_csv_v4_*" | ForEach-Object Name)
    $o = & $py export_csv_v4.py --session $U $B 2>&1
    $exOk = ($LASTEXITCODE -eq 0)
    $new = @(Get-ChildItem (Join-Path $rv "outputs") -Directory -Filter "export_csv_v4_*" | Where-Object { $before -notcontains $_.Name })
    if (-not $exOk -or $new.Count -ne 1) { $fail++; "export: FAILED (exit $LASTEXITCODE): $(($o | Select-Object -Last 3) -join ' ')" }
    else { "export: $($new[0].FullName)" }
    $ErrorActionPreference = "Stop"
} finally { Pop-Location }
$timeout = (Get-Content (Join-Path (Split-Path $PSScriptRoot -Parent) "unity\Robotics-Warehouse\WarehouseProjectURP\Assets\WarehouseRobot\Scenario\Config\trial_plan_v4.json") -Raw | ConvertFrom-Json).development_timeout_s
$manifest = Join-Path $rv "outputs\step5_sessions.json"
$m = if (Test-Path $manifest) { Get-Content $manifest -Raw | ConvertFrom-Json } else { [pscustomobject]@{ note = "step 5 sessions (finals_v4/step5_session_checks.ps1); paths relative to robot_vision/"; sessions = @() } }
$rel = { param($x) $f = [System.IO.Path]::GetFullPath($x); if ($f.StartsWith($rv + "\", [System.StringComparison]::OrdinalIgnoreCase)) { $f.Substring($rv.Length + 1) -replace '\\', '/' } else { $f } }
$entry = [pscustomobject]@{ setting = $Setting; unity = (& $rel $U); bridge = (& $rel $B); export = $(if ($new.Count -eq 1) { & $rel $new[0].FullName } else { "" });
                            timeout_s = $timeout; checks_passed = ($fail -eq 0); launcher_log = (& $rel (Resolve-Path $Launcher).Path) }
$m.sessions = @($m.sessions | Where-Object { $_.setting -ne $Setting }) + $entry
[System.IO.File]::WriteAllText($manifest, ($m | ConvertTo-Json -Depth 5))
"manifest: $manifest ($Setting)"
# run outputs keep no absolute path (CLAUDE.md; robot_vision/tests/test_run_paths.py): the console transcript under outputs/ is
# rewritten with paths relative to the repository root, and any other absolute path (the Unity editor) as <abs>/...
$lt = [System.IO.File]::ReadAllText((Resolve-Path $Launcher).Path)
$lt = $lt.Replace($repoRoot + "\", "").Replace($repoRoot, ".")
$lt = [regex]::Replace($lt, '(?<![A-Za-z0-9])[A-Za-z]:[\\/](?!/)', '<abs>/')
[System.IO.File]::WriteAllText((Resolve-Path $Launcher).Path, $lt, (New-Object System.Text.UTF8Encoding($true)))
"$(if ($fail) { "CHECKS FAILED: $fail" } else { 'ALL CHECKS PASSED' })"
exit $fail
