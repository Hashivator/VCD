from datetime import datetime
from colorama import Fore, Style

LEVEL_COLORS = {
    "INFO": Fore.GREEN,
    "WARN": Fore.YELLOW,
    "ERROR": Fore.RED,
    "SUCCESS": Fore.CYAN,
    "STEP": Fore.MAGENTA,
    "DEBUG": Fore.WHITE,
}


def log(msg: str, level: str = "INFO") -> None:
    now = datetime.now().strftime("%H:%M:%S")
    color = LEVEL_COLORS.get(level, Fore.WHITE)
    print(
        f"{Style.DIM}[{now}]{Style.RESET_ALL} {color}{level:7s}{Style.RESET_ALL} {msg}",
        flush=True,
    )
