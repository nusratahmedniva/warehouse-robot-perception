"""Machine state recorded with every trial session (2026-10-22, AUDIT.md section 9 run protocol).

read() never raises: what cannot be read is reported as unknown with the reason. Recorded in the bridge run's
run_info.json (machine_state) and printed by the trial launchers, which warn when the power mode is not the highest
performance mode or the machine runs on battery.

- Windows: the power mode of Settings > System > Power (the "overlay" scheme in the registry,
  HKLM\\SYSTEM\\CurrentControlSet\\Control\\Power\\User\\PowerSchemes, ActiveOverlayAcPowerScheme / ...Dc...), the active
  power plan (powercfg /getactivescheme) and the power source (psutil battery; no battery = mains).
- macOS: Low Power Mode and the power source (pmset -g, pmset -g batt).

    python -m bridge.machine_state          prints the state as JSON
"""

from __future__ import annotations

import json
import platform
import re
import subprocess

# Windows 10/11 power-mode overlay GUIDs (Settings > System > Power > Power mode).
WINDOWS_OVERLAYS = {
    "ded574b5-45a0-4f42-8737-46345c09c238": "Best performance",
    "00000000-0000-0000-0000-000000000000": "Balanced",
    "961cc777-2547-4f9d-8174-7d86181b8a7a": "Best power efficiency",
}
BEST = {"Windows": "Best performance", "Darwin": "Low Power Mode off"}


def _run(cmd: list[str]) -> str:
    # Windows console tools write in the console's code page: UTF-8 under a UTF-8 console, else the OEM code page
    # (codec "oem", Windows only).
    raw = subprocess.run(cmd, capture_output=True, timeout=5, check=False).stdout
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("oem" if platform.system() == "Windows" else "utf-8", errors="replace")


def power_source() -> str:
    try:
        import psutil
        b = psutil.sensors_battery()
    except Exception as e:  # noqa: BLE001 (report, never raise)
        return f"unknown ({type(e).__name__})"
    if b is None:
        return "mains (no battery)"
    return "mains (charger connected)" if b.power_plugged else "battery"


def _windows(state: dict) -> None:
    import winreg
    on_battery = state["power_source"] == "battery"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Power\User\PowerSchemes") as k:
            name = "ActiveOverlayDcPowerScheme" if on_battery else "ActiveOverlayAcPowerScheme"
            try:
                guid = str(winreg.QueryValueEx(k, name)[0]).lower()
            except FileNotFoundError:
                guid = "00000000-0000-0000-0000-000000000000"      # no overlay set: Balanced
        state["power_mode"] = WINDOWS_OVERLAYS.get(guid, f"unknown overlay {guid}")
        state["power_mode_source"] = f"registry {name}"
    except OSError as e:
        state["power_mode"] = f"unknown ({e})"
    m = re.search(r"GUID:\s*([0-9a-f-]+)\s*\((.*)\)", _run(["powercfg", "/getactivescheme"]))
    state["power_plan"] = f"{m.group(2)} ({m.group(1)})" if m else "unknown"


def _macos(state: dict) -> None:
    m = re.search(r"lowpowermode\s+(\d)", _run(["pmset", "-g"]))
    state["power_mode"] = ("Low Power Mode on" if m.group(1) == "1" else "Low Power Mode off") if m else "unknown"
    batt = _run(["pmset", "-g", "batt"])
    if "AC Power" in batt:
        state["power_source"] = "mains (charger connected)"
    elif "Battery Power" in batt:
        state["power_source"] = "battery"


def read() -> dict:
    system = platform.system()
    state = {"system": system, "platform": platform.platform(), "power_source": power_source(), "power_mode": "unknown"}
    try:
        if system == "Windows":
            _windows(state)
        elif system == "Darwin":
            _macos(state)
    except Exception as e:  # noqa: BLE001 (report, never raise)
        state["error"] = f"{type(e).__name__}: {e}"
    state["warnings"] = warnings(state)
    return state


def warnings(state: dict) -> list[str]:
    out = []
    best = BEST.get(state.get("system", ""))
    if best and state.get("power_mode") != best:
        out.append(f"power mode is '{state.get('power_mode')}', the run protocol asks for '{best}'")
    if state.get("power_source") == "battery":
        out.append("running on battery: connect the charger (run protocol)")
    return out


if __name__ == "__main__":
    print(json.dumps(read(), indent=2))
