#!/usr/bin/env bash
# Trial launcher (macOS / Linux): starts the bridge server in GUIDE mode with VISION perception for one task.
#
# The only supported way to run trials. It always runs
#     python -m bridge.server --mode guide --perception vision --task <Task> --resource-log
# from robot_vision/.venv (hello mode, a 0.2 m/s bridge test, is never used here). launch_prep.py first refuses a task
# other than the one in configs/trials.json (or the git-ignored trials.local.json the Unity trial runner prefers) and
# prints the machine state (power mode, power source) with run-protocol warnings (AUDIT.md section 9).
#
#   ./run_trials.sh Task1                         server in this terminal; then press Play in the Unity Editor
#   ./run_trials.sh Task1 --unity-batch           also runs the session headless (TrialBatchPlay), stops the server
#                                                 when Unity quits, then runs hri_trials.py, hri_analysis.py and
#                                                 hri_session_check.py
#   ./run_trials.sh Task1 --unity-batch --trials 5   development only: 5 trials instead of trial_count (launcher-
#                                                 written trials.local.json, removed afterwards; refused in final mode)
# Unity: $UNITY_EDITOR, else /Applications/Unity/Hub/Editor/<ProjectVersion>/Unity.app/Contents/MacOS/Unity.
set -euo pipefail

usage() { echo "usage: $0 Task1|Task2 [--unity-batch] [--trials N]" >&2; exit 2; }
TASK="${1:-}"
case "$TASK" in Task1|Task2) ;; *) usage ;; esac
shift
BATCH=""
TRIALS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --unity-batch) BATCH=1 ;;
    --trials) [ $# -ge 2 ] || usage; TRIALS="$2"; shift ;;
    *) usage ;;
  esac
  shift
done

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$HERE/.venv/bin/python"
PROJECT="$(cd "$HERE/../unity/Robotics-Warehouse/WarehouseProjectURP" && pwd)"
[ -x "$PY" ] || { echo "No project venv at $PY (see README: create robot_vision/.venv first)." >&2; exit 1; }

cd "$HERE"
PREP=(launch_prep.py --task "$TASK")
if [ -n "$TRIALS" ]; then
  PREP+=(--trials "$TRIALS")
  trap '"$PY" launch_prep.py --cleanup' EXIT
fi
"$PY" "${PREP[@]}"
echo "[run_trials] GUIDE mode, VISION perception, task $TASK"

SERVER_ARGS=(-m bridge.server --mode guide --perception vision --task "$TASK" --resource-log)
if [ -z "$BATCH" ]; then
  echo "[run_trials] when the server says 'listening', press Play in Unity. Ctrl+C stops the server."
  set +e
  "$PY" "${SERVER_ARGS[@]}"
  exit $?
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
set +e
"$PY" hri_session_check.py --unity "$TRIALS_DIR" --bridge "$BRIDGE_DIR"
exit $?
