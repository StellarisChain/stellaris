from util.logging import log
from typing import Optional
import inspect

def deprecated(reason, logger: Optional[log] = None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            # If no logger provided, try to find one from the function context
            actual_logger = logger
            if actual_logger is None:
                # Try to get logger from self.logger (for class methods)
                if args and hasattr(args[0], 'logger'):
                    actual_logger = args[0].logger
                # Try to get logger from function's module or globals
                elif hasattr(func, '__globals__') and 'logger' in func.__globals__:
                    actual_logger = func.__globals__['logger']
                # Try to get logger from the calling frame's locals
                else:
                    frame = inspect.currentframe()
                    try:
                        caller_frame = frame.f_back
                        if caller_frame and 'logger' in caller_frame.f_locals:
                            actual_logger = caller_frame.f_locals['logger']
                        elif caller_frame and 'self' in caller_frame.f_locals:
                            caller_self = caller_frame.f_locals['self']
                            if hasattr(caller_self, 'logger'):
                                actual_logger = caller_self.logger
                    finally:
                        del frame
            
            if actual_logger is None:
                actual_logger = log()
            
            # Log the deprecation warning if we found a logger
            if actual_logger:
                actual_logger.warning(f"Warning: {func.__name__} is deprecated. {reason}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator