import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: str = "./app.log") -> logging.Logger:
    logger = logging.getLogger("tx_scanner")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    if not logger.handlers:
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(fmt)
        logger.addHandler(console)

        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger
