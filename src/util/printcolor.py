from colorama import init, Fore, Style, Back

def print_color(message: str, color: str) -> None:
    print(f"{color}{message}{Style.RESET_ALL}")