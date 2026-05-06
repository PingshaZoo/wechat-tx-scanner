import sqlite3
import json
import logging
from pathlib import Path
from scanner.file_scanner import FileEntry

logger = logging.getLogger("tx_scanner.dedup")

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_path TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_mtime REAL NOT NULL,
    is_transaction INTEGER DEFAULT 0,
    transaction_data TEXT,
    processed_at TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'success'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_path_size_mtime
    ON processed_files(file_path, file_size, file_mtime);
"""


class Deduplicator:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript(SCHEMA)

    def is_processed(self, entry: FileEntry) -> bool:
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_files WHERE file_path=? AND file_size=? AND file_mtime=?",
                (entry.path, entry.size, entry.mtime)
            ).fetchone()
            return row is not None

    def mark_processed(self, entry: FileEntry, is_transaction: bool = False,
                       transaction_data: dict | None = None, status: str = "success"):
        with self._get_conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO processed_files
                   (file_path, file_size, file_mtime, is_transaction, transaction_data, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    entry.path,
                    entry.size,
                    entry.mtime,
                    1 if is_transaction else 0,
                    json.dumps(transaction_data, ensure_ascii=False) if transaction_data else None,
                    status,
                )
            )

    def get_all_transactions(self) -> list[dict]:
        """Return all previously found transactions for Excel rebuild."""
        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT file_path, transaction_data FROM processed_files WHERE is_transaction=1 AND transaction_data IS NOT NULL"
            ).fetchall()

        results = []
        for file_path, data_json in rows:
            try:
                data = json.loads(data_json)
                data["对应图片"] = file_path
                results.append(data)
            except json.JSONDecodeError:
                logger.warning("Corrupt transaction_data for: %s", file_path)
        return results

    def get_stats(self) -> dict:
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM processed_files").fetchone()[0]
            tx_count = conn.execute("SELECT COUNT(*) FROM processed_files WHERE is_transaction=1").fetchone()[0]
            errors = conn.execute("SELECT COUNT(*) FROM processed_files WHERE status!='success'").fetchone()[0]
        return {"total_processed": total, "transactions_found": tx_count, "errors": errors}
