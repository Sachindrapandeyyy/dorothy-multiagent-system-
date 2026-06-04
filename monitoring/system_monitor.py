"""Dorothy OS v2.0 — Real-Time System Telemetry Monitor.

Provides CPU, RAM, disk, battery, network, GPU, and per-process stats
using ``psutil`` (and ``nvidia-smi`` when available).  Results are cached
for 1 second to prevent excessive polling when multiple agents query
stats in rapid succession.

All heavy ``psutil`` calls are wrapped in ``asyncio.to_thread`` so the
monitor can be used from async code without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import subprocess
import time
from typing import Any, Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS: float = 1.0
"""How long cached telemetry is considered fresh."""


class SystemMonitor:
    """Real-time system telemetry collector.

    Example::

        monitor = SystemMonitor()

        # Synchronous (fine for CLI / agent threads)
        stats = monitor.get_stats()

        # Async (preferred in the orchestrator loop)
        stats = await monitor.get_stats_async()
        procs = await monitor.get_top_processes_async(n=5)
    """

    def __init__(self) -> None:
        """Initialise caches and probe for GPU availability."""
        self._stats_cache: Optional[Dict[str, Any]] = None
        self._stats_cache_ts: float = 0.0

        self._procs_cache: Optional[List[Dict[str, Any]]] = None
        self._procs_cache_ts: float = 0.0

        self._has_nvidia_smi: bool = shutil.which("nvidia-smi") is not None
        logger.debug(
            "SystemMonitor initialised — nvidia-smi available: %s",
            self._has_nvidia_smi,
        )

    # -----------------------------------------------------------------
    # Synchronous API
    # -----------------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        """Collect a full system telemetry snapshot.

        Returns a dict with keys:

        * ``cpu_percent`` – overall CPU usage (float).
        * ``ram``         – ``{total_gb, used_gb, percent}``.
        * ``disk``        – list of per-partition dicts.
        * ``battery``     – ``{percent, plugged_in, secs_left}`` or ``None``.
        * ``network``     – ``{bytes_sent, bytes_recv}`` (cumulative).
        * ``gpu``         – list of GPU dicts or empty list.

        Results are cached for ``_CACHE_TTL_SECONDS``.
        """
        now = time.monotonic()
        if self._stats_cache is not None and (now - self._stats_cache_ts) < _CACHE_TTL_SECONDS:
            return self._stats_cache

        stats: Dict[str, Any] = {}

        # ── CPU ─────────────────────────────────────────────────────
        try:
            stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            stats["cpu_count_logical"] = psutil.cpu_count(logical=True)
            stats["cpu_count_physical"] = psutil.cpu_count(logical=False)
            stats["cpu_freq_mhz"] = None
            freq = psutil.cpu_freq()
            if freq:
                stats["cpu_freq_mhz"] = round(freq.current, 1)
        except Exception as exc:
            logger.warning("Failed to read CPU stats: %s", exc)
            stats["cpu_percent"] = 0.0

        # ── RAM ─────────────────────────────────────────────────────
        try:
            mem = psutil.virtual_memory()
            stats["ram"] = {
                "total_gb": round(mem.total / (1024 ** 3), 2),
                "used_gb": round(mem.used / (1024 ** 3), 2),
                "available_gb": round(mem.available / (1024 ** 3), 2),
                "percent": mem.percent,
            }
        except Exception as exc:
            logger.warning("Failed to read RAM stats: %s", exc)
            stats["ram"] = {"total_gb": 0, "used_gb": 0, "available_gb": 0, "percent": 0}

        # ── Disk ────────────────────────────────────────────────────
        try:
            partitions = psutil.disk_partitions(all=False)
            disk_list: List[Dict[str, Any]] = []
            for part in partitions:
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    disk_list.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024 ** 3), 2),
                        "used_gb": round(usage.used / (1024 ** 3), 2),
                        "free_gb": round(usage.free / (1024 ** 3), 2),
                        "percent": usage.percent,
                    })
                except PermissionError:
                    continue
            stats["disk"] = disk_list
        except Exception as exc:
            logger.warning("Failed to read disk stats: %s", exc)
            stats["disk"] = []

        # ── Battery ─────────────────────────────────────────────────
        try:
            battery = psutil.sensors_battery()
            if battery is not None:
                stats["battery"] = {
                    "percent": battery.percent,
                    "plugged_in": battery.power_plugged,
                    "secs_left": battery.secsleft if battery.secsleft != psutil.POWER_TIME_UNLIMITED else -1,
                }
            else:
                stats["battery"] = None
        except Exception as exc:
            logger.warning("Failed to read battery stats: %s", exc)
            stats["battery"] = None

        # ── Network ─────────────────────────────────────────────────
        try:
            net = psutil.net_io_counters()
            stats["network"] = {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
                "packets_sent": net.packets_sent,
                "packets_recv": net.packets_recv,
            }
        except Exception as exc:
            logger.warning("Failed to read network stats: %s", exc)
            stats["network"] = {"bytes_sent": 0, "bytes_recv": 0, "packets_sent": 0, "packets_recv": 0}

        # ── GPU (nvidia-smi) ────────────────────────────────────────
        stats["gpu"] = self._query_gpu()

        self._stats_cache = stats
        self._stats_cache_ts = now
        return stats

    def get_top_processes(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the *n* most CPU-hungry processes.

        Args:
            n: Number of processes to return (default 10).

        Returns:
            List of dicts with ``name``, ``pid``, ``cpu_percent``,
            ``memory_mb``.
        """
        now = time.monotonic()
        if self._procs_cache is not None and (now - self._procs_cache_ts) < _CACHE_TTL_SECONDS:
            return self._procs_cache[:n]

        procs: List[Dict[str, Any]] = []
        try:
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info"]):
                try:
                    info = proc.info  # type: ignore[attr-defined]
                    mem_info = info.get("memory_info")
                    mem_mb = round(mem_info.rss / (1024 ** 2), 1) if mem_info else 0.0
                    procs.append({
                        "pid": info["pid"],
                        "name": info.get("name", "unknown"),
                        "cpu_percent": info.get("cpu_percent", 0.0) or 0.0,
                        "memory_mb": mem_mb,
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
        except Exception as exc:
            logger.warning("Failed to enumerate processes: %s", exc)

        # Sort by CPU descending, then by memory descending
        procs.sort(key=lambda p: (p["cpu_percent"], p["memory_mb"]), reverse=True)

        self._procs_cache = procs
        self._procs_cache_ts = now
        return procs[:n]

    # -----------------------------------------------------------------
    # Async wrappers
    # -----------------------------------------------------------------

    async def get_stats_async(self) -> Dict[str, Any]:
        """Async wrapper for :meth:`get_stats` (runs in a thread).

        Returns:
            Same dict as ``get_stats()``.
        """
        return await asyncio.to_thread(self.get_stats)

    async def get_top_processes_async(self, n: int = 10) -> List[Dict[str, Any]]:
        """Async wrapper for :meth:`get_top_processes`.

        Args:
            n: Number of processes to return.

        Returns:
            Same list as ``get_top_processes(n)``.
        """
        return await asyncio.to_thread(self.get_top_processes, n)

    # -----------------------------------------------------------------
    # GPU helper
    # -----------------------------------------------------------------

    def _query_gpu(self) -> List[Dict[str, Any]]:
        """Query NVIDIA GPU stats via ``nvidia-smi``.

        Returns an empty list if ``nvidia-smi`` is not installed or fails.
        """
        if not self._has_nvidia_smi:
            return []

        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
            if result.returncode != 0:
                logger.debug("nvidia-smi returned code %d", result.returncode)
                return []

            gpus: List[Dict[str, Any]] = []
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": int(parts[0]),
                        "name": parts[1],
                        "utilization_percent": float(parts[2]),
                        "memory_used_mb": float(parts[3]),
                        "memory_total_mb": float(parts[4]),
                        "temperature_c": float(parts[5]),
                    })
            return gpus

        except FileNotFoundError:
            self._has_nvidia_smi = False
            return []
        except subprocess.TimeoutExpired:
            logger.warning("nvidia-smi timed out")
            return []
        except Exception as exc:
            logger.warning("nvidia-smi query failed: %s", exc)
            return []
