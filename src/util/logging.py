import inspect
import logging
import os
from typing import Optional
from colorama import init, Fore, Style, Back
from util.printcolor import print_color
from util.jsonreader import read_json_from_namespace

dev_config = read_json_from_namespace("config.dev") or {}
debugging = dev_config.get("debug", False)

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
        print_color(f"[INFO]: {message}", Fore.WHITE)

    def error(self, message: str) -> None:
        self.Logger.error(f"{message}")
        print_color(f"[ERROR]: {message}", Fore.RED)

    def debug(self, message: str) -> None:
        self.Logger.debug(f"{message}")
        if debugging:
            print_color(f"[DEBUG]: {message}", Fore.CYAN)

    def warning(self, message: str) -> None:
        self.Logger.warning(f"{message}")
        print_color(f"[WARNING]: {message}", Fore.YELLOW)

    def critical(self, message: str) -> None:
        self.Logger.critical(f"{message}")
        print_color(f"[CRITICAL]: {message}", Fore.RED + Back.YELLOW)