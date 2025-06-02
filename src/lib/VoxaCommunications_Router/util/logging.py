import inspect
import logging
import os
from typing import Optional

def set_log_config(log_id: str, force: Optional[bool] = True) -> None:
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(filename=f"logs/{log_id}.log", level=logging.DEBUG, force=force)

class log:
    def __init__(self):
        Caller_Frame = inspect.stack()[1]
        Caller_Module = inspect.getmodule(Caller_Frame[0])
        self.Module_Name = Caller_Module.__name__ if Caller_Module else "__main__"
        self.Logger = logging.getLogger(self.Module_Name)
        self.Logger.setLevel(logging.DEBUG)

    def info(self, message: str) -> None:
        self.Logger.info(f"{message}")
        print(f"[INFO]: {message}")

    def error(self, message: str) -> None:
        self.Logger.error(f"{message}")
        print(f"[ERROR]: {message}")

    def debug(self, message: str) -> None:
        self.Logger.debug(f"{message}")
        print(f"[DEBUG]: {message}")

    def warning(self, message: str) -> None:
        self.Logger.warning(f"{message}")
        print(f"[WARNING]: {message}")

    def critical(self, message: str) -> None:
        self.Logger.critical(f"{message}")
        print(f"[CRITICAL]: {message}")