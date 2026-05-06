import logging
import time
from pathlib import Path

from scanner.file_scanner import FileEntry
from core.pipeline import process_file, ProcessResult

logger = logging.getLogger("tx_scanner.watcher")


def start_watching(config: dict):
    """Watch configured WeChat directories for new files in real-time."""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        logger.error("watchdog not installed. Install with: pip install watchdog")
        return

    scan_cfg = config["wechat"]
    out_cfg = config["output"]
    decoded_dir = Path(out_cfg["decoded_images_dir"])
    decoded_dir.mkdir(parents=True, exist_ok=True)

    from ai_client.qwen_client import QwenClient
    from core.deduplicator import Deduplicator
    from writer.excel_writer import ExcelWriter

    ai_client = QwenClient(config)
    dedup = Deduplicator(config["state"]["db_path"])
    writer = ExcelWriter(out_cfg["excel_path"], out_cfg["sheet_name"], out_cfg["columns"])
    writer.initialize()

    allowed_exts = {e.lower() if e.startswith(".") else f".{e.lower()}"
                    for e in scan_cfg["file_extensions"]}
    pending = {}  # path -> first_seen_time

    class WeChatHandler(FileSystemEventHandler):
        def on_created(self, event):
            if event.is_directory:
                return
            path = Path(event.src_path)
            if path.suffix.lower() not in allowed_exts:
                return
            if path.name.startswith("."):
                return

            # Debounce: Windows may fire multiple events
            key = str(path)
            now = time.time()
            if key in pending and (now - pending[key]) < 5:
                return
            pending[key] = now

            # Wait for file copy to complete (not ideal but practical)
            time.sleep(1)

            try:
                stat = path.stat()
            except OSError:
                return

            entry = FileEntry(
                path=str(path.resolve()),
                size=stat.st_size,
                mtime=stat.st_mtime,
                extension=path.suffix.lower(),
            )

            min_size = scan_cfg["min_file_size_kb"] * 1024
            max_size = scan_cfg["max_file_size_mb"] * 1024 * 1024
            if entry.size < min_size or entry.size > max_size:
                return

            logger.info("New file detected: %s", path.name)
            result, tx_data = process_file(entry, ai_client, dedup, decoded_dir)

            if result == ProcessResult.TRANSACTION_FOUND:
                writer.append_rows([tx_data])
                logger.info("  -> TRANSACTION: %s | %.2f",
                            tx_data.get("交易方"), tx_data.get("交易金额"))

    observer = Observer()
    for scan_path in scan_cfg["scan_paths"]:
        p = Path(scan_path)
        if p.exists():
            observer.schedule(WeChatHandler(), str(p), recursive=True)
            logger.info("Watching: %s", p)

    observer.start()
    logger.info("=== Watching for new files... (Ctrl+C to stop) ===")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Stopped watching")
    observer.join()
