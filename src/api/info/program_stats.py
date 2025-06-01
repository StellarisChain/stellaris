import os
import sys
import platform
import psutil
from typing import Dict, Any
from fastapi import Response
from util.logging import log
from src import __version__

def handler():# -> dict[str, Any]:
    """
    Endpoint to get program and system statistics
    Returns system info, resource usage, and runtime metrics
    """
    logger = log()
    logger.info("Program stats endpoint called")
    
    # Collect system information
    stats = {
        "system": {
            "os": platform.system(),
            "os_version": platform.release(),
            "python": platform.python_version(),
            "hostname": platform.node(),
            "arch": platform.machine()
        },
        "resources": {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used": psutil.virtual_memory().used,
            "memory_total": psutil.virtual_memory().total,
            "disk_percent": psutil.disk_usage('/').percent,
            "disk_used": psutil.disk_usage('/').used,
            "disk_total": psutil.disk_usage('/').total
        },
        "process": {
            "pid": os.getpid(),
            "memory_usage": psutil.Process(os.getpid()).memory_info().rss,
            "cpu_usage": psutil.Process(os.getpid()).cpu_percent()
        },
        "program": {
            "version": __version__,
            "python_executable": sys.executable,
            "python_path": sys.path,
            "start_time": psutil.Process(os.getpid()).create_time()
        },
        "runtime": {
            "uptime": psutil.boot_time(),
            "current_time": psutil.Process(os.getpid()).create_time()
        }
    }
    
    return stats