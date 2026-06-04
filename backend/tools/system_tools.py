import time
import psutil
import logging
import subprocess
import sys
from typing import Dict, Any, List

# Core Audio & COM imports for Windows
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _audio_available = True
except Exception:
    _audio_available = False

logger = logging.getLogger("JARVIS.SystemTools")

# Globals for measuring network speed asynchronously
_last_net_time = time.time()
_last_net_bytes = psutil.net_io_counters()

def get_system_volume() -> float:
    """Get Windows master audio volume scalar (0.0 to 1.0)."""
    if not _audio_available or sys.platform != "win32":
        return 0.5
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return float(volume.GetMasterVolumeLevelScalar())
    except Exception as e:
        logger.debug(f"Error getting volume: {e}")
        return 0.5

def set_system_volume(level: float):
    """Set Windows master audio volume scalar (0.0 to 1.0)."""
    if not _audio_available or sys.platform != "win32":
        return
    try:
        # Cap level between 0.0 and 1.0
        level = max(0.0, min(1.0, level))
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level, None)
    except Exception as e:
        logger.error(f"Error setting volume: {e}")

def get_system_brightness() -> int:
    """Get monitor brightness using WMI CIM instance (0 to 100)."""
    if sys.platform != "win32":
        return 50
    try:
        cmd = 'powershell -Command "(Get-CimInstance -Namespace root/WMI -ClassName WmiMonitorBrightness).CurrentBrightness"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
        out = res.stdout.strip()
        if out.isdigit():
            return int(out)
        return 50
    except Exception as e:
        logger.debug(f"Error getting brightness: {e}")
        return 50

def set_system_brightness(level: int):
    """Set monitor brightness using WMI methods (0 to 100)."""
    if sys.platform != "win32":
        return
    try:
        level = max(0, min(100, level))
        cmd = f'powershell -Command "(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"'
        subprocess.run(cmd, shell=True, capture_output=True, timeout=3)
    except Exception as e:
        logger.error(f"Error setting brightness: {e}")

def is_wifi_enabled() -> bool:
    """Check if WiFi network adapter is enabled."""
    if sys.platform != "win32":
        return False
    try:
        cmd = 'netsh interface show interface "WiFi"'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
        return "Enabled" in res.stdout
    except Exception:
        return False

def toggle_wifi(enable: bool) -> bool:
    """Toggle WiFi network adapter state."""
    if sys.platform != "win32":
        return False
    try:
        state = "enabled" if enable else "disabled"
        cmd = f'netsh interface set interface "WiFi" {state}'
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=3)
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Error toggling wifi: {e}")
        return False

def get_network_speed() -> Dict[str, float]:
    """Calculate upload and download speed in KBps since last measurement."""
    global _last_net_time, _last_net_bytes
    current_time = time.time()
    current_bytes = psutil.net_io_counters()
    elapsed = current_time - _last_net_time
    
    if elapsed <= 0:
        return {"upload_kbps": 0.0, "download_kbps": 0.0}
    
    sent_diff = current_bytes.bytes_sent - _last_net_bytes.bytes_sent
    recv_diff = current_bytes.bytes_recv - _last_net_bytes.bytes_recv
    
    # Bytes to KB per second
    upload_kbps = (sent_diff / 1024.0) / elapsed
    download_kbps = (recv_diff / 1024.0) / elapsed
    
    _last_net_time = current_time
    _last_net_bytes = current_bytes
    
    return {
        "upload_kbps": round(upload_kbps, 2),
        "download_kbps": round(download_kbps, 2)
    }

async def get_system_stats() -> Dict[str, Any]:
    """Retrieve current system resources consumption and network speed."""
    try:
        # CPU
        cpu = psutil.cpu_percent(interval=None)
        
        # RAM
        virtual_mem = psutil.virtual_memory()
        ram = {
            "used_gb": round(virtual_mem.used / (1024**3), 2),
            "total_gb": round(virtual_mem.total / (1024**3), 2),
            "percent": virtual_mem.percent
        }
        
        # Disk stats
        disk_list = []
        for partition in psutil.disk_partitions(all=False):
            # Check fixed disks to avoid external/optical drives blocking on Windows
            if "cdrom" in partition.opts or not partition.mountpoint:
                continue
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                drive_name = partition.mountpoint.replace("\\", "")
                disk_list.append({
                    "drive": drive_name if drive_name else "/",
                    "used_gb": round(usage.used / (1024**3), 2),
                    "total_gb": round(usage.total / (1024**3), 2),
                    "percent": usage.percent
                })
            except (PermissionError, FileNotFoundError):
                # Skip inaccessible drives
                continue
                
        # Battery stats
        battery = psutil.sensors_battery()
        if battery:
            battery_info = {
                "percent": battery.percent,
                "charging": battery.power_plugged
            }
        else:
            battery_info = {
                "percent": 100,
                "charging": True
            }
            
        # Network stats
        network = get_network_speed()
        
        stats = {
            "cpu": cpu,
            "ram": ram,
            "disk": disk_list,
            "battery": battery_info,
            "network": network,
            "volume": round(get_system_volume(), 2),
            "brightness": get_system_brightness(),
            "wifi_enabled": is_wifi_enabled()
        }
        return stats
    except Exception as e:
        logger.error(f"Error gathering system stats: {e}", exc_info=True)
        return {
            "cpu": 0.0,
            "ram": {"used_gb": 0.0, "total_gb": 0.0, "percent": 0.0},
            "disk": [],
            "battery": {"percent": 100, "charging": True},
            "network": {"upload_kbps": 0.0, "download_kbps": 0.0},
            "volume": 0.5,
            "brightness": 50,
            "wifi_enabled": False
        }

async def get_top_processes(n: int = 10) -> List[Dict[str, Any]]:
    """Retrieve top N processes consuming most CPU."""
    processes = []
    # Trigger first measurement
    psutil.cpu_percent(interval=None)
    
    for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            # We filter out processes that don't have proper names
            if proc.info['name']:
                processes.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "cpu_percent": round(proc.info['cpu_percent'] or 0.0, 1),
                    "memory_percent": round(proc.info['memory_percent'] or 0.0, 2)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
    # Sort processes by cpu_percent descending
    processes.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return processes[:n]

