"""
Dorothy OS v2.0 — System Telemetry & Control Tools
Provides async-compatible system monitoring, volume/brightness control, and network telemetry.
"""

import os
import sys
import logging
import asyncio
import time
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("Dorothy.Tools.System")

# ─── Network Speed Tracking ──────────────────────────────────────────────────
_last_net_io = None
_last_net_time = None


async def get_system_stats() -> Dict[str, Any]:
    """Get comprehensive system telemetry: CPU, RAM, disk, battery, network speeds."""
    return await asyncio.to_thread(_get_system_stats_sync)


def _get_system_stats_sync() -> Dict[str, Any]:
    """Synchronous system stats collector (runs in thread)."""
    import psutil

    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.5)

    # RAM
    ram = psutil.virtual_memory()
    ram_data = {
        "total_gb": round(ram.total / (1024 ** 3), 2),
        "used_gb": round(ram.used / (1024 ** 3), 2),
        "available_gb": round(ram.available / (1024 ** 3), 2),
        "percent": ram.percent,
    }

    # Disk partitions
    disk_data = []
    try:
        for partition in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disk_data.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total_gb": round(usage.total / (1024 ** 3), 2),
                    "used_gb": round(usage.used / (1024 ** 3), 2),
                    "free_gb": round(usage.free / (1024 ** 3), 2),
                    "percent": usage.percent,
                })
            except PermissionError:
                continue
    except Exception as e:
        logger.warning(f"Could not read disk partitions: {e}")

    # Battery
    battery_data = {"percent": 100, "plugged": True, "secs_left": -1}
    try:
        battery = psutil.sensors_battery()
        if battery:
            battery_data = {
                "percent": battery.percent,
                "plugged": battery.power_plugged,
                "secs_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
            }
    except Exception:
        pass

    # Network speed
    net_speed = _get_network_speed_sync()

    return {
        "cpu": cpu_percent,
        "ram": ram_data,
        "disk": disk_data,
        "battery": battery_data,
        "network": net_speed,
    }


def _get_network_speed_sync() -> Dict[str, float]:
    """Calculate network upload/download speeds using delta I/O counters."""
    global _last_net_io, _last_net_time
    import psutil

    current_io = psutil.net_io_counters()
    current_time = time.time()

    if _last_net_io is None or _last_net_time is None:
        _last_net_io = current_io
        _last_net_time = current_time
        return {"upload_kbps": 0.0, "download_kbps": 0.0}

    elapsed = current_time - _last_net_time
    if elapsed <= 0:
        return {"upload_kbps": 0.0, "download_kbps": 0.0}

    upload_kbps = round((current_io.bytes_sent - _last_net_io.bytes_sent) / elapsed / 1024, 2)
    download_kbps = round((current_io.bytes_recv - _last_net_io.bytes_recv) / elapsed / 1024, 2)

    _last_net_io = current_io
    _last_net_time = current_time

    return {"upload_kbps": max(0, upload_kbps), "download_kbps": max(0, download_kbps)}


async def get_top_processes(n: int = 10) -> List[Dict[str, Any]]:
    """Get top N CPU-consuming processes."""
    return await asyncio.to_thread(_get_top_processes_sync, n)


def _get_top_processes_sync(n: int = 10) -> List[Dict[str, Any]]:
    """Synchronous process scanner (runs in thread)."""
    import psutil

    processes = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
        try:
            info = proc.info
            mem_mb = round(info["memory_info"].rss / (1024 ** 2), 1) if info.get("memory_info") else 0
            processes.append({
                "pid": info["pid"],
                "name": info["name"],
                "cpu_percent": info["cpu_percent"] or 0,
                "memory_mb": mem_mb,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return processes[:n]


async def get_gpu_stats() -> Optional[Dict[str, Any]]:
    """Attempt to get NVIDIA GPU stats via nvidia-smi. Returns None if unavailable."""
    return await asyncio.to_thread(_get_gpu_stats_sync)


def _get_gpu_stats_sync() -> Optional[Dict[str, Any]]:
    """Query nvidia-smi for GPU telemetry."""
    import subprocess

    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 5:
                return {
                    "name": parts[0].strip(),
                    "temperature_c": int(parts[1].strip()),
                    "utilization_percent": int(parts[2].strip()),
                    "memory_used_mb": int(parts[3].strip()),
                    "memory_total_mb": int(parts[4].strip()),
                }
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        pass
    return None


# ─── Volume Control (Windows only via pycaw) ─────────────────────────────────

async def get_system_volume() -> Dict[str, Any]:
    """Get current system volume level (0-100)."""
    if sys.platform != "win32":
        return {"success": False, "error": "Volume control is Windows-only."}
    return await asyncio.to_thread(_get_volume_sync)


def _get_volume_sync() -> Dict[str, Any]:
    """Read system volume using pycaw COM interface."""
    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, 'Activate'):
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        else:
            interface = devices.device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            
        volume = interface.QueryInterface(IAudioEndpointVolume)
        current = volume.GetMasterVolumeLevelScalar()
        muted = volume.GetMute()
        return {"success": True, "volume": round(current * 100), "muted": bool(muted)}
    except Exception as e:
        logger.error(f"Volume read failed: {e}")
        return {"success": False, "error": str(e)}


async def set_system_volume(level: int) -> Dict[str, Any]:
    """Set system volume to a value between 0 and 100."""
    if sys.platform != "win32":
        return {"success": False, "error": "Volume control is Windows-only."}
    level = max(0, min(100, level))
    return await asyncio.to_thread(_set_volume_sync, level)


def _set_volume_sync(level: int) -> Dict[str, Any]:
    """Write system volume using pycaw COM interface."""
    try:
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        if hasattr(devices, 'Activate'):
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        else:
            interface = devices.device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            
        volume = interface.QueryInterface(IAudioEndpointVolume)
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return {"success": True, "volume": level, "message": f"Volume set to {level}%."}
    except Exception as e:
        logger.error(f"Volume set failed: {e}")
        return {"success": False, "error": str(e)}


# ─── Brightness Control (Windows WMI) ────────────────────────────────────────

async def set_system_brightness(level: int) -> Dict[str, Any]:
    """Set screen brightness (0-100) using PowerShell WMI."""
    if sys.platform != "win32":
        return {"success": False, "error": "Brightness control is Windows-only."}
    level = max(0, min(100, level))
    return await asyncio.to_thread(_set_brightness_sync, level)


def _set_brightness_sync(level: int) -> Dict[str, Any]:
    """Set brightness via WMI PowerShell command."""
    import subprocess

    try:
        cmd = (
            f'powershell -NoProfile -Command "'
            f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods)"
            f'.WmiSetBrightness(1, {level})"'
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {"success": True, "brightness": level, "message": f"Brightness set to {level}%."}
        return {"success": False, "error": result.stderr.strip() or "Unknown error"}
    except Exception as e:
        logger.error(f"Brightness set failed: {e}")
        return {"success": False, "error": str(e)}


# ─── WiFi Toggle (Windows netsh) ─────────────────────────────────────────────

async def toggle_wifi(enable: bool = True) -> Dict[str, Any]:
    """Enable or disable the WiFi adapter via netsh."""
    if sys.platform != "win32":
        return {"success": False, "error": "WiFi toggle is Windows-only."}
    return await asyncio.to_thread(_toggle_wifi_sync, enable)


def _toggle_wifi_sync(enable: bool) -> Dict[str, Any]:
    """Toggle WiFi adapter using netsh interface command."""
    import subprocess

    action = "enable" if enable else "disable"
    try:
        cmd = f'netsh interface set interface "WiFi" {action}'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            return {"success": True, "wifi": action + "d", "message": f"WiFi adapter {action}d successfully."}
        return {"success": False, "error": result.stderr.strip() or "Requires admin privileges."}
    except Exception as e:
        logger.error(f"WiFi toggle failed: {e}")
        return {"success": False, "error": str(e)}
