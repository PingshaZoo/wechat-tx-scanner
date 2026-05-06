#!/usr/bin/env python3
"""WeChat Transaction Image Recognition System.
Scans WeChat image files, uses AI vision to identify transactions,
and writes extracted data to Excel.
"""

import argparse
import sys
from pathlib import Path

from utils.config_loader import load_config
from utils.logger import setup_logging


def cmd_test_ai(config: dict):
    """Test AI backend connectivity."""
    logger = setup_logging("INFO", config["logging"]["file"])
    logger.info("Testing AI connectivity...")

    api_key = config["ai"]["api_key"]
    if not api_key:
        logger.error("No API key configured. Set DASHSCOPE_API_KEY env var or api_key in config.yaml")
        sys.exit(1)

    from ai_client.qwen_client import QwenClient
    client = QwenClient(config)
    ok = client.check_connectivity()
    if ok:
        logger.info("AI backend is ready.")
    else:
        logger.error("AI backend check failed. Check API key and network.")
        sys.exit(1)


def cmd_scan(config: dict, force: bool = False):
    """Run a one-time scan."""
    logger = setup_logging(config["logging"]["level"], config["logging"]["file"])

    api_key = config["ai"]["api_key"]
    if not api_key:
        logger.error("No API key configured. Set DASHSCOPE_API_KEY env var or api_key in config.yaml")
        sys.exit(1)

    from core.pipeline import run_scan
    stats = run_scan(config, force=force)

    logger.info("=== Scan Complete ===")
    logger.info("Total files scanned : %d", stats["scanned"])
    logger.info("New files processed: %d", stats["new"])
    logger.info("Transactions found  : %d", stats["transactions"])
    logger.info("Non-transactions    : %d", stats["not_transactions"])
    logger.info("Already processed   : %d", stats["skipped"])
    logger.info("Decode failures     : %d", stats["decode_failed"])
    logger.info("AI errors           : %d", stats["ai_errors"])
    logger.info("Output: %s", config["output"]["excel_path"])


def cmd_watch(config: dict):
    """Start continuous file watching."""
    logger = setup_logging(config["logging"]["level"], config["logging"]["file"])

    api_key = config["ai"]["api_key"]
    if not api_key:
        logger.error("No API key configured. Set DASHSCOPE_API_KEY env var or api_key in config.yaml")
        sys.exit(1)

    from core.watcher import start_watching
    start_watching(config)


def main():
    parser = argparse.ArgumentParser(
        description="WeChat Transaction Image Recognition System"
    )
    parser.add_argument(
        "--mode", choices=["once", "watch"], default="once",
        help="Scan mode: once (one-time scan) or watch (continuous monitoring)"
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-process all files, ignoring dedup database"
    )
    parser.add_argument(
        "--test-ai", action="store_true",
        help="Test AI backend connectivity and exit"
    )

    args = parser.parse_args()
    config = load_config(args.config)

    if args.test_ai:
        cmd_test_ai(config)
    elif args.mode == "watch":
        cmd_watch(config)
    else:
        cmd_scan(config, force=args.force)


if __name__ == "__main__":
    main()
