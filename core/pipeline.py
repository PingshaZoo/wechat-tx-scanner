import logging
from pathlib import Path
from enum import Enum

from scanner.file_scanner import find_image_files, FileEntry
from decoder.dat_decoder import decode_dat_file
from ai_client.qwen_client import QwenClient
from parser.transaction_parser import parse_ai_response
from writer.excel_writer import ExcelWriter
from core.deduplicator import Deduplicator

logger = logging.getLogger("tx_scanner.pipeline")


class ProcessResult(Enum):
    TRANSACTION_FOUND = "transaction_found"
    NOT_TRANSACTION = "not_transaction"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    DECODE_FAILED = "decode_failed"
    AI_ERROR = "ai_error"


def process_file(entry: FileEntry, ai_client: QwenClient, dedup: Deduplicator,
                 decoded_dir: Path) -> tuple[ProcessResult, dict | None]:
    """Process a single file through the complete pipeline. Returns (result, transaction_data)."""

    if dedup.is_processed(entry):
        logger.debug("Skipping duplicate: %s", Path(entry.path).name)
        return ProcessResult.SKIPPED_DUPLICATE, None

    # Determine image path (decode .dat if needed)
    image_path = Path(entry.path)

    if entry.extension == ".dat":
        decoded = decode_dat_file(image_path, decoded_dir)
        if decoded is None:
            logger.info("Decode failed: %s", image_path.name)
            dedup.mark_processed(entry, is_transaction=False, status="decode_failed")
            return ProcessResult.DECODE_FAILED, None
        image_path = decoded
        is_temp = True
    else:
        is_temp = False

    # Send to AI
    try:
        result = ai_client.analyze_image(image_path)
    except Exception as e:
        logger.error("AI error for %s: %s", Path(entry.path).name, e)
        dedup.mark_processed(entry, is_transaction=False, status=f"ai_error: {e}")
        if is_temp:
            image_path.unlink(missing_ok=True)
        return ProcessResult.AI_ERROR, None

    # Clean up temp file
    if is_temp:
        image_path.unlink(missing_ok=True)

    # Mark processed
    if result.is_transaction and result.transaction_data:
        result.transaction_data["对应图片"] = entry.path
        dedup.mark_processed(entry, is_transaction=True, transaction_data=result.transaction_data)
        return ProcessResult.TRANSACTION_FOUND, result.transaction_data
    else:
        dedup.mark_processed(entry, is_transaction=False)
        return ProcessResult.NOT_TRANSACTION, None


def run_scan(config: dict, force: bool = False) -> dict:
    """Run a full one-time scan. Returns statistics dict."""
    scan_cfg = config["wechat"]
    out_cfg = config["output"]

    logger.info("=== Starting scan ===")

    # Initialize modules
    ai_client = QwenClient(config)
    dedup = Deduplicator(config["state"]["db_path"])
    writer = ExcelWriter(out_cfg["excel_path"], out_cfg["sheet_name"], out_cfg["columns"])
    decoded_dir = Path(out_cfg["decoded_images_dir"])

    # Ensure output dirs exist
    decoded_dir.mkdir(parents=True, exist_ok=True)

    # Ensure Excel exists with headers
    writer.initialize()

    # Scan for files
    files = find_image_files(
        scan_cfg["scan_paths"],
        scan_cfg["file_extensions"],
        scan_cfg["min_file_size_kb"],
        scan_cfg["max_file_size_mb"],
    )
    logger.info("Found %d files to check", len(files))

    # Filter out already processed (unless --force)
    if force:
        logger.warning("Force mode: re-processing all files")
        new_files = files
    else:
        new_files = [f for f in files if not dedup.is_processed(f)]
        logger.info("%d new files to process (%d already processed)",
                    len(new_files), len(files) - len(new_files))

    # Process each file
    transactions = []
    stats = {"scanned": len(files), "new": len(new_files), "transactions": 0,
             "not_transactions": 0, "skipped": len(files) - len(new_files),
             "decode_failed": 0, "ai_errors": 0}

    for i, entry in enumerate(new_files, 1):
        logger.info("[%d/%d] %s", i, len(new_files), Path(entry.path).name)
        result, tx_data = process_file(entry, ai_client, dedup, decoded_dir)

        if result == ProcessResult.TRANSACTION_FOUND:
            transactions.append(tx_data)
            stats["transactions"] += 1
            logger.info("  -> TRANSACTION: %s | %s | %.2f",
                        tx_data.get("交易方"), tx_data.get("支付方式"), tx_data.get("交易金额"))
        elif result == ProcessResult.NOT_TRANSACTION:
            stats["not_transactions"] += 1
        elif result == ProcessResult.DECODE_FAILED:
            stats["decode_failed"] += 1
        elif result == ProcessResult.AI_ERROR:
            stats["ai_errors"] += 1

    # Write to Excel
    if transactions:
        writer.append_rows(transactions)
        logger.info("Wrote %d transaction(s) to Excel", len(transactions))
    else:
        logger.info("No new transactions found")

    return stats
