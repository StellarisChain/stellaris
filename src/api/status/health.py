import datetime
from util.logging import log

def handler():
    """
    Endpoint to get system health status
    Returns the current status of the system and uptime
    """
    logger = log()
    logger.info("Health status endpoint called")
    
    # Simple health check response
    status = {
        "status": "online",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0",
        "healthy": True,
        "message": "System is operating normally"
    }
    
    return status