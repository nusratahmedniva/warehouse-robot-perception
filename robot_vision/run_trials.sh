#!/usr/bin/env bash
# Trial launcher (macOS / Linux): starts the bridge server in GUIDE mode with VISION perception for one task.
#
# The only supported way to run trials. It always runs
#     python -m bridge.server --mode guide --perception vision --task <Task>
# from robot_vision/.venv (hello mode, a 0.2 m/s bridge test, is never used here). It refuses to start when
# configs/trials.json (or the git-ignored trials.local.json the Unity trial runner prefers) names another task.
#
#   ./run_trials.sh Task1               server in this terminal; then press Play in the Unity Editor; Ctrl+C stops it
#   ./run_trials.sh Task1 --unity-batch also runs the session headless (TrialBatchPlay), stops the server when Unity
#                                       quits, then runs hri_trials.py, hri_analysis.py and hri_session_check.py
# Unity: $UNITY_EDITOR, else /Applications/Unity/Hub/Editor/<ProjectVersion>/Unity.app/Contents/MacOS/Unity.
set -euo pipefail

TASK="${1:-}"
BATCH="${2:-}"
case "$TASK" in Task1|Task2) ;; *) echo "usage: $0 Task1|Task2 [--unity-batch]" >&2; exit 2 ;; esac
case "$BATCH" in ""|--unity-batch) ;; *) echo "usage: $0 Task1|Task2 [--unity-batch]" >&2; exit 2 ;; esac

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$HERE/.venv/bin/python"
PROJECT="$(cd "$HERE/../unity/Robotics-Warehouse/WarehouseProjectURP" && pwd)"
[ -x "$PY" ] || { echo "No project venv at $PY (see README: create robot_vision/.venv first)." >&2; exit 1; }

TRIALS="$HERE/configs/trials.local.json"
[ -f "$TRIALS" ] || TRIALS="$HERE/configs/trials.json"
CFG_TASK="$("$PY" -c 'import json,sys; c=json.load(open(sys.argv[1], encoding="utf-8")); print(c["task"], c["mode"])' "$TRIALS")"
if [ "${CFG_TASK%% *}" != "$TASK" ]; then
  echo "$TRIALS says task '${CFG_TASK%% *}' but you asked for $TASK. Set \"task\" there (and \"mode\") first." >&2
  exit 1
fi
echo "[run_trials] GUIDE mode, VISION perception, task $TASK (${CFG_TASK#* }, $(basename "$TRIALS"))"

cd "$HERE"
SERVER_ARGS=(-m bridge.server --mode guide --perception vision --task "$TASK")
if [ -z "$BATCH" ]; then
  echo "[run_trials] when the server says 'listening', press Play in Unity. Ctrl+C stops the server."
  exec "$PY" "${SERVER_ARGS[@]}"
fi

if [ -z "${UNITY_EDITOR:-}" ]; then
  VERSION="$(sed -n 's/^m_EditorVersion: *//p' "$PROJECT/ProjectSettings/ProjectVersion.txt")"
  UNITY_EDITOR="/Applications/Unity/Hub/Editor/$VERSION/Unity.app/Contents/MacOS/Unity"
fi
[ -x "$UNITY_EDITOR" ] || { echo "Unity not found at $UNITY_EDITOR (set UNITY_EDITOR)." >&2; exit 1; }

MARK="$(mktemp)"                       # folders newer than this file belong to this session
"$PY" "${SERVER_ARGS[@]}" --exit-on-disconnect &
SERVER=$!
UNITY_LOG="${TMPDIR:-/tmp}/unity_trials_$(date +%Y%m%d_%H%M%S).log"
echo "[run_trials] Unity batch session (log $UNITY_LOG); the server warms up first, Unity waits for it."
set +e
"$UNITY_EDITOR" -batchmode -projectPath "$PROJECT" -executeMethod WarehouseRobot.ScenarioEditor.TrialBatchPlay.Run \
  -trialTimeout 3600 -logFile "$UNITY_LOG"
echo "[run_trials] Unity exited with $?"
for _ in $(seq 120); do kill -0 "$SERVER" 2>/dev/null || break; sleep 1; done
kill "$SERVER" 2>/dev/null
wait "$SERVER" 2>/dev/null
set -e

newest() { find outputs -maxdepth 1 -type d -name "$1" -newer "$MARK" | sort | tail -1; }
TRIALS_DIR="$(newest "trials_*_${TASK}_*")"
BRIDGE_DIR="$(newest "bridge_guide_*")"
[ -n "$TRIALS_DIR" ] && [ -n "$BRIDGE_DIR" ] || { echo "no new trials_* / bridge_guide_* folder under outputs" >&2; exit 1; }
echo "[run_trials] Unity: $TRIALS_DIR  Python: $BRIDGE_DIR"
"$PY" hri_trials.py --unity "$TRIALS_DIR" --bridge "$BRIDGE_DIR" | tail -1
"$PY" hri_analysis.py "$(newest 'hri_trials_*')" | tail -1
rm -f "$MARK"
"$PY" hri_session_check.py --unity "$TRIALS_DIR" --bridge "$BRIDGE_DIR"
