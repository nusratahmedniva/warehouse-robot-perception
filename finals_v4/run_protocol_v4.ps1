param([Parameter(Mandatory = $true)][string]$Label)
# The run-protocol note before a v4 session (B11 criterion 5; AUDIT.md section 9 run protocol): free memory, power scheme, the
# programs on the watch list that are still running, and the git commit. Writes robot_vision\outputs\run_protocol_<Label>_<time>.txt
# (git-ignored, a new file every time, never overwritten) and prints its path. It closes nothing.
$ErrorActionPreference = "Stop"
$repo = Split-Path $PSScriptRoot -Parent
$out = Join-Path $repo "robot_vision\outputs"
$file = Join-Path $out ("run_protocol_{0}_{1:yyyyMMdd_HHmmss}.txt" -f $Label, (Get-Date))
if (Test-Path $file) { throw "$file exists; not overwritten" }
$os = Get-CimInstance Win32_OperatingSystem
$watch = 'chrome', 'msedge', 'firefox', 'claude', 'Claude', 'vmmem', 'vmmemWSL', 'warp-svc', 'NVIDIA Overlay', 'nvcontainer', 'Teams', 'OneDrive', 'Discord', 'steam'
$running = Get-Process | Where-Object { $watch -contains $_.ProcessName } | Group-Object ProcessName |
    ForEach-Object { "{0} x{1} ({2:N0} MB)" -f $_.Name, $_.Count, (($_.Group | Measure-Object WorkingSet64 -Sum).Sum / 1MB) }
$lines = @(
    "run protocol note: $Label",
    "time: $(Get-Date -Format s)",
    ("free memory: {0:N0} MB of {1:N0} MB" -f ($os.FreePhysicalMemory / 1KB), ($os.TotalVisibleMemorySize / 1KB)),
    "power scheme: $((powercfg /getactivescheme) -join ' ')",
    "programs on the watch list still running: $(if ($running) { $running -join '; ' } else { 'none' })",
    "git commit: $(git -C $repo rev-parse HEAD)",
    "git status (short): $(((git -C $repo status --short) -join ' | '))"
)
[System.IO.File]::WriteAllLines($file, $lines)
$lines | ForEach-Object { "  $_" }
$file
