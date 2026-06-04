"""
Dorothy OS v2.0 — File Operations Tools
Safe filesystem operations with path validation to block dangerous system directories.
"""

import os
import shutil
import glob
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("Dorothy.Tools.File")

# Blocked path prefixes — operations on these directories are denied
BLOCKED_PATHS = [
    "c:\\windows",
    "c:\\boot",
    "c:\\$recycle.bin",
    "c:\\recovery",
    "c:\\system volume information",
    "c:\\programdata\\microsoft",
]


def _validate_path(path: str) -> bool:
    """Check if a file path is safe to operate on. Returns True if safe."""
    if not path:
        return False
    normalized = os.path.normpath(path).lower()
    for blocked in BLOCKED_PATHS:
        if normalized.startswith(blocked):
            logger.warning(f"Blocked access to protected path: {path}")
            return False
    return True


async def read_file(path: str) -> Dict[str, Any]:
    """Read the text contents of a file on the local filesystem."""
    if not _validate_path(path):
        return {"success": False, "error": f"Access denied: '{path}' is in a protected directory."}
    return await asyncio.to_thread(_read_file_sync, path)


def _read_file_sync(path: str) -> Dict[str, Any]:
    """Synchronous file reader."""
    try:
        if not os.path.isfile(path):
            return {"success": False, "error": f"File not found: '{path}'."}
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        size_kb = round(os.path.getsize(path) / 1024, 2)
        return {"success": True, "path": path, "content": content, "size_kb": size_kb}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def write_file(path: str, content: str) -> Dict[str, Any]:
    """Write or overwrite text content to a file."""
    if not _validate_path(path):
        return {"success": False, "error": f"Access denied: '{path}' is in a protected directory."}
    return await asyncio.to_thread(_write_file_sync, path, content)


def _write_file_sync(path: str, content: str) -> Dict[str, Any]:
    """Synchronous file writer."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "bytes_written": len(content.encode("utf-8")),
                "message": f"File written: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def create_file(path: str, content: str = "") -> Dict[str, Any]:
    """Create a new file. Fails if file already exists."""
    if not _validate_path(path):
        return {"success": False, "error": f"Access denied: '{path}' is in a protected directory."}
    return await asyncio.to_thread(_create_file_sync, path, content)


def _create_file_sync(path: str, content: str = "") -> Dict[str, Any]:
    """Synchronous file creator."""
    try:
        if os.path.exists(path):
            return {"success": False, "error": f"File already exists: '{path}'. Use write_file to overwrite."}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": path, "message": f"File created: {path}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def list_directory(path: str) -> Dict[str, Any]:
    """List the files and directories inside a specific path."""
    if not _validate_path(path):
        return {"success": False, "error": f"Access denied: '{path}' is in a protected directory."}
    return await asyncio.to_thread(_list_dir_sync, path)


def _list_dir_sync(path: str) -> Dict[str, Any]:
    """Synchronous directory lister."""
    try:
        if not os.path.isdir(path):
            return {"success": False, "error": f"Directory not found: '{path}'."}
        entries = []
        for item in os.listdir(path):
            full = os.path.join(path, item)
            entry = {"name": item, "is_dir": os.path.isdir(full)}
            if os.path.isfile(full):
                try:
                    entry["size_kb"] = round(os.path.getsize(full) / 1024, 2)
                except OSError:
                    entry["size_kb"] = 0
            entries.append(entry)
        return {"success": True, "path": path, "entries": entries, "count": len(entries)}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def delete_file(path: str) -> Dict[str, Any]:
    """Delete a file or recursively delete a directory."""
    if not _validate_path(path):
        return {"success": False, "error": f"Access denied: '{path}' is in a protected directory."}
    return await asyncio.to_thread(_delete_file_sync, path)


def _delete_file_sync(path: str) -> Dict[str, Any]:
    """Synchronous file/directory deleter."""
    try:
        if os.path.isfile(path):
            os.remove(path)
            return {"success": True, "path": path, "message": f"File deleted: {path}"}
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return {"success": True, "path": path, "message": f"Directory deleted recursively: {path}"}
        else:
            return {"success": False, "error": f"Path not found: '{path}'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def move_file(src: str, dest: str) -> Dict[str, Any]:
    """Move or rename a file or directory."""
    if not _validate_path(src) or not _validate_path(dest):
        return {"success": False, "error": "Access denied: source or destination is in a protected directory."}
    return await asyncio.to_thread(_move_file_sync, src, dest)


def _move_file_sync(src: str, dest: str) -> Dict[str, Any]:
    """Synchronous file mover."""
    try:
        if not os.path.exists(src):
            return {"success": False, "error": f"Source path not found: '{src}'."}
        shutil.move(src, dest)
        return {"success": True, "src": src, "dest": dest, "message": f"Moved: {src} → {dest}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def copy_file(src: str, dest: str) -> Dict[str, Any]:
    """Copy a file or directory to a new location."""
    if not _validate_path(src) or not _validate_path(dest):
        return {"success": False, "error": "Access denied: source or destination is in a protected directory."}
    return await asyncio.to_thread(_copy_file_sync, src, dest)


def _copy_file_sync(src: str, dest: str) -> Dict[str, Any]:
    """Synchronous file copier."""
    try:
        if not os.path.exists(src):
            return {"success": False, "error": f"Source path not found: '{src}'."}
        if os.path.isdir(src):
            shutil.copytree(src, dest)
        else:
            os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
            shutil.copy2(src, dest)
        return {"success": True, "src": src, "dest": dest, "message": f"Copied: {src} → {dest}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def search_files(directory: str, pattern: str) -> Dict[str, Any]:
    """Search for files within a directory matching a glob pattern."""
    if not _validate_path(directory):
        return {"success": False, "error": f"Access denied: '{directory}' is in a protected directory."}
    return await asyncio.to_thread(_search_files_sync, directory, pattern)


def _search_files_sync(directory: str, pattern: str) -> Dict[str, Any]:
    """Synchronous glob search."""
    try:
        if not os.path.isdir(directory):
            return {"success": False, "error": f"Directory not found: '{directory}'."}
        search_pattern = os.path.join(directory, "**", pattern)
        matches = glob.glob(search_pattern, recursive=True)
        results = [{"path": m, "is_dir": os.path.isdir(m)} for m in matches[:100]]
        return {"success": True, "directory": directory, "pattern": pattern,
                "matches": results, "count": len(results),
                "truncated": len(matches) > 100}
    except Exception as e:
        return {"success": False, "error": str(e)}
