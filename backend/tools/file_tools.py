import os
import shutil
import glob
import logging
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger("JARVIS.FileTools")

def validate_path(path: str) -> str:
    """Resolve and validate path. Raises PermissionError if path is unsafe."""
    abs_path = os.path.abspath(path)
    abs_lower = abs_path.lower()
    
    # Safety Check: Block critical system folders to protect system integrity
    blocked_prefixes = [
        "c:\\windows",
        "c:\\boot",
        "c:\\system32",  # typically covered by c:\windows but good to be explicit
        "c:\\$recycle.bin",
        "c:\\recovery",
    ]
    
    for blocked in blocked_prefixes:
        if abs_lower.startswith(blocked):
            raise PermissionError(f"Access to critical system path '{abs_path}' is blocked for system safety, Boss.")
            
    return abs_path

async def read_file(path: str) -> Dict[str, Any]:
    """Read contents of a file safely."""
    try:
        validated = await asyncio.to_thread(validate_path, path)
        if not await asyncio.to_thread(os.path.exists, validated):
            return {"success": False, "error": f"File does not exist: {path}"}
            
        if not await asyncio.to_thread(os.path.path.isfile if hasattr(os.path, 'path') else os.path.isfile, validated):
            return {"success": False, "error": f"Path is not a file: {path}"}
            
        def _read():
            with open(validated, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
                
        content = await asyncio.to_thread(_read)
        return {"success": True, "content": content, "path": validated}
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def write_file(path: str, content: str) -> Dict[str, Any]:
    """Write or overwrite content to a file."""
    try:
        validated = await asyncio.to_thread(validate_path, path)
        
        # Ensure parent directories exist
        parent = os.path.dirname(validated)
        if parent:
            await asyncio.to_thread(os.makedirs, parent, exist_ok=True)
            
        def _write():
            with open(validated, 'w', encoding='utf-8') as f:
                f.write(content)
                
        await asyncio.to_thread(_write)
        return {"success": True, "message": f"Successfully wrote to {path}", "path": validated}
    except Exception as e:
        logger.error(f"Error writing file {path}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def create_file(path: str, content: str = "") -> Dict[str, Any]:
    """Create a new file. Fails if file already exists."""
    try:
        validated = await asyncio.to_thread(validate_path, path)
        if await asyncio.to_thread(os.path.exists, validated):
            return {"success": False, "error": f"File already exists: {path}"}
        return await write_file(validated, content)
    except Exception as e:
        return {"success": False, "error": str(e)}

async def list_directory(path: str) -> Dict[str, Any]:
    """List directory contents including files and directories."""
    try:
        validated = await asyncio.to_thread(validate_path, path)
        if not await asyncio.to_thread(os.path.exists, validated):
            return {"success": False, "error": f"Directory does not exist: {path}"}
            
        if not await asyncio.to_thread(os.path.isdir, validated):
            return {"success": False, "error": f"Path is not a directory: {path}"}
            
        def _list():
            items = []
            for item in os.listdir(validated):
                full_item_path = os.path.join(validated, item)
                is_dir = os.path.isdir(full_item_path)
                size = os.path.getsize(full_item_path) if not is_dir else 0
                items.append({
                    "name": item,
                    "type": "directory" if is_dir else "file",
                    "size_bytes": size,
                    "path": full_item_path
                })
            return items
            
        items = await asyncio.to_thread(_list)
        return {"success": True, "items": items, "directory": validated}
    except Exception as e:
        logger.error(f"Error listing directory {path}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def delete_file(path: str) -> Dict[str, Any]:
    """Delete a file or recursively delete a directory."""
    try:
        validated = await asyncio.to_thread(validate_path, path)
        if not await asyncio.to_thread(os.path.exists, validated):
            return {"success": False, "error": f"Path does not exist: {path}"}
            
        def _delete():
            if os.path.isdir(validated):
                shutil.rmtree(validated)
                return f"Successfully deleted directory {path} and all its contents"
            else:
                os.remove(validated)
                return f"Successfully deleted file {path}"
                
        message = await asyncio.to_thread(_delete)
        return {"success": True, "message": message}
    except Exception as e:
        logger.error(f"Error deleting path {path}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def move_file(src: str, dest: str) -> Dict[str, Any]:
    """Move or rename a file or directory."""
    try:
        val_src = await asyncio.to_thread(validate_path, src)
        val_dest = await asyncio.to_thread(validate_path, dest)
        
        if not await asyncio.to_thread(os.path.exists, val_src):
            return {"success": False, "error": f"Source does not exist: {src}"}
            
        # Create destination folder if not exist
        dest_parent = os.path.dirname(val_dest)
        if dest_parent:
            await asyncio.to_thread(os.makedirs, dest_parent, exist_ok=True)
            
        await asyncio.to_thread(shutil.move, val_src, val_dest)
        return {"success": True, "message": f"Successfully moved {src} to {dest}", "src": val_src, "dest": val_dest}
    except Exception as e:
        logger.error(f"Error moving {src} to {dest}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def copy_file(src: str, dest: str) -> Dict[str, Any]:
    """Copy a file or directory."""
    try:
        val_src = await asyncio.to_thread(validate_path, src)
        val_dest = await asyncio.to_thread(validate_path, dest)
        
        if not await asyncio.to_thread(os.path.exists, val_src):
            return {"success": False, "error": f"Source does not exist: {src}"}
            
        dest_parent = os.path.dirname(val_dest)
        if dest_parent:
            await asyncio.to_thread(os.makedirs, dest_parent, exist_ok=True)
            
        def _copy():
            if os.path.isdir(val_src):
                shutil.copytree(val_src, val_dest, dirs_exist_ok=True)
            else:
                shutil.copy2(val_src, val_dest)
                
        await asyncio.to_thread(_copy)
        return {"success": True, "message": f"Successfully copied {src} to {dest}", "src": val_src, "dest": val_dest}
    except Exception as e:
        logger.error(f"Error copying {src} to {dest}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}

async def search_files(directory: str, pattern: str) -> Dict[str, Any]:
    """Search for files in a directory matching a glob pattern."""
    try:
        validated_dir = await asyncio.to_thread(validate_path, directory)
        if not await asyncio.to_thread(os.path.exists, validated_dir):
            return {"success": False, "error": f"Search directory does not exist: {directory}"}
            
        def _search():
            # Use glob to recursively search matches
            search_pattern = os.path.join(validated_dir, "**", pattern)
            matches = glob.glob(search_pattern, recursive=True)
            # Map matches to relative path
            results = []
            for match in matches:
                try:
                    # Validate each match as a precaution
                    validate_path(match)
                    is_dir = os.path.isdir(match)
                    results.append({
                        "name": os.path.basename(match),
                        "type": "directory" if is_dir else "file",
                        "path": match
                    })
                except PermissionError:
                    continue
            return results
            
        results = await asyncio.to_thread(_search)
        return {"success": True, "matches": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Error searching files in {directory} with pattern {pattern}: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
