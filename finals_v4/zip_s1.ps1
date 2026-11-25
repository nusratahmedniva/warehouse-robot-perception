param(
    [string]$OutDir = "E:\final_sittings_for_anisha",   # the folder outside the repository where Anisha reads the zips (the finals' zips are there too)
    [string[]]$Extra = @(),                             # extra files or folders (the power-mode line, notes on what deviated, the plan table s1_plan_*.txt)
    [switch]$DryRun                                     # list what would be packed; write nothing
)
# ONE zip of every S1 session (post-freeze supplementary experiment S1; Unity addendum 14): per cell entry of robot_vision\outputs\s1_runs.json (written by
# run_s1.ps1) the Unity session folder (whole: truth.jsonl, decisions.csv through the bridge run, run files, config_used, leak_test, S1 markers), the
# bridge run folder (whole: v4_log.jsonl, stop_reading.jsonl, messages.jsonl, summary.json, config_used), the launcher's transcript, crash watch,
# server and Unity logs and the run-protocol note, plus s1_runs.json, every s1_plan_*.txt, every -Extra, and the S1 config. MANIFEST.json inside: every
# file with its size and SHA-256, the git commit, the cells found and what was missing. Read-only on outputs\; nothing is moved or deleted; the zip is
# never overwritten (the time is in its name). After writing: the archive is re-opened and every entry's SHA-256 is checked, then the zip's own SHA-256
# is printed and written to <zip>.sha256 ("<hex>  <zip name>", as sha256sum -c reads it). Anisha reads the zip in place; nothing in it is run.
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$rv = Join-Path $repo "robot_vision"
$outputs = Join-Path $rv "outputs"
$manifestFile = Join-Path $outputs "s1_runs.json"
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$zipPath = Join-Path $OutDir "s1_supplementary_$stamp.zip"
$problems = @()
if (-not (Test-Path $manifestFile)) { Write-Host "REFUSED: $manifestFile does not exist: no S1 cell was recorded by run_s1.ps1"; exit 2 }
$entries = @(Get-Content $manifestFile -Raw | ConvertFrom-Json)
$repoFull = [System.IO.Path]::GetFullPath($repo).TrimEnd('\') + '\'
$outFull = [System.IO.Path]::GetFullPath($OutDir).TrimEnd('\') + '\'
if ($outFull.StartsWith($repoFull, [System.StringComparison]::OrdinalIgnoreCase)) { Write-Host "REFUSED: -OutDir is inside the repository ($OutDir)"; exit 2 }
if (Test-Path $zipPath) { Write-Host "REFUSED: $zipPath exists; not overwritten"; exit 2 }
$files = New-Object System.Collections.Generic.List[object]    # @{ Path; Name }
function AddTree($path, $prefix) {
    if (-not (Test-Path $path)) { $script:problems += "missing: $path"; return }
    $root = (Resolve-Path $path).Path
    if (Test-Path $root -PathType Container) {
        foreach ($f in Get-ChildItem $root -Recurse -File -Force) { $script:files.Add(@{ Path = $f.FullName; Name = ($prefix + "/" + $f.FullName.Substring($root.Length).TrimStart('\').Replace('\', '/')) }) }
    } else { $script:files.Add(@{ Path = $root; Name = ($prefix + "/" + (Split-Path $root -Leaf)) }) }
}
$cells = @()
foreach ($e in $entries) {
    $dir = "cells/$($e.character)_$($e.setting)_part$($e.part)"
    $cells += [pscustomobject]@{ character = $e.character; setting = $e.setting; part = $e.part; unity_session = $e.unity_session; bridge_run = $e.bridge_run; valid = $e.valid }
    AddTree (Join-Path $outputs $e.unity_session) "$dir/$($e.unity_session)"
    AddTree (Join-Path $outputs $e.bridge_run) "$dir/$($e.bridge_run)"
    foreach ($n in $e.protocol_note, $e.transcript, $e.crashwatch, $e.server_log, $e.server_err_log, $e.unity_log) { if ($n) { AddTree (Join-Path $outputs $n) "$dir/logs" } }
}
AddTree $manifestFile "s1"
foreach ($f in Get-ChildItem $outputs -File -Filter "s1_plan_*.txt" -ErrorAction SilentlyContinue) { AddTree $f.FullName "s1/plan" }
AddTree (Join-Path $repo "unity\Robotics-Warehouse\WarehouseProjectURP\Assets\WarehouseRobot\Avatar\Config\s1_supplementary.json") "s1/config"
foreach ($x in $Extra) { AddTree $x "extra" }
$gitCommit = (git -C $repo rev-parse HEAD).Trim()
$gitBranch = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
$names = @{}
foreach ($f in $files) { if ($names.ContainsKey($f.Name)) { $problems += "duplicate entry name $($f.Name)" } else { $names[$f.Name] = $true } }
$expected = 12
$cellKeys = @($cells | ForEach-Object { "$($_.character)/$($_.setting)" } | Sort-Object -Unique)
Write-Host "S1 zip: $($entries.Count) recorded part(s) of $($cellKeys.Count) cell(s) (12 expected for the full experiment), $($files.Count) files"
foreach ($c in $cells) { Write-Host "    $($c.character) / $($c.setting) part $($c.part): $($c.unity_session) + $($c.bridge_run)$(if (-not $c.valid) { '  (INVALID: packed as it stands)' })" }
foreach ($p in $problems) { Write-Host "    PROBLEM: $p" }
if ($DryRun) { Write-Host "DRY RUN: nothing was written."; exit 0 }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
$manifest = [ordered]@{
    what = "post-freeze supplementary experiment S1 (AUDIT.md 16.36 + 16.37, Unity addendum 14): exploratory, never pooled with the finals"
    created = $stamp; git_commit = $gitCommit; git_branch = $gitBranch; cells_found = $cellKeys.Count; cells_expected = $expected
    cells = $cells; missing_or_problems = $problems; files = @()
}
$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
try {
    $list = @()
    foreach ($f in $files) {
        $h = (Get-FileHash $f.Path -Algorithm SHA256).Hash.ToLower()
        $item = Get-Item $f.Path
        $null = [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.Path, $f.Name, [System.IO.Compression.CompressionLevel]::Optimal)
        $list += [ordered]@{ name = $f.Name; bytes = $item.Length; sha256 = $h }
    }
    $manifest.files = $list
    $mtext = ($manifest | ConvertTo-Json -Depth 6)
    $entry = $zip.CreateEntry("MANIFEST.json")
    $sw = New-Object System.IO.StreamWriter($entry.Open(), (New-Object System.Text.UTF8Encoding $false))
    $sw.Write($mtext + "`n"); $sw.Dispose()
} finally { $zip.Dispose() }
# verify: every entry re-read and compared with the manifest
$check = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
$bad = 0
try {
    $byName = @{}
    foreach ($e in $manifest.files) { $byName[$e.name] = $e.sha256 }
    foreach ($e in $check.Entries) {
        if ($e.FullName -eq "MANIFEST.json") { continue }
        $sha = [System.Security.Cryptography.SHA256]::Create()
        $s = $e.Open(); $h = ([BitConverter]::ToString($sha.ComputeHash($s)) -replace '-', '').ToLower(); $s.Dispose()
        if ($byName[$e.FullName] -ne $h) { $bad++; Write-Host "    MISMATCH: $($e.FullName)" }
    }
    if ($check.Entries.Count -ne $manifest.files.Count + 1) { $bad++; Write-Host "    entry count $($check.Entries.Count) differs from the manifest ($($manifest.files.Count) + MANIFEST.json)" }
} finally { $check.Dispose() }
if ($bad) { Write-Host "ZIP CHECK FAILED ($bad): $zipPath is not to be sent"; exit 1 }
$zipHash = (Get-FileHash $zipPath -Algorithm SHA256).Hash.ToLower()
[System.IO.File]::WriteAllText("$zipPath.sha256", "$zipHash  $(Split-Path $zipPath -Leaf)`n", (New-Object System.Text.UTF8Encoding $false))
Write-Host ""
Write-Host "zip:    $zipPath"
Write-Host "size:   $((Get-Item $zipPath).Length) bytes, $($files.Count + 1) entries (every entry re-read and its SHA-256 equals the manifest)"
Write-Host "SHA-256 $zipHash"
