# WeChat Transaction Image Recognition System

## Overview
Windows-based system that scans local WeChat file storage for images, uses AI vision (Qwen-VL via DashScope) to identify transaction-related images, extracts structured transaction data, and writes results to Excel.

## Key Features
- Scans WeChat `FileStorage/Image/`, `FileStorage/File/`, `FileStorage/MsgAttach/` directories
- XOR-decrypts WeChat `.dat` encrypted image files (covers WeChat v3.x; v4.0+ AES files are skipped)
- AI vision classification: identifies receipts, invoices, transfer screenshots (WeChat/Alipay/Bank/UnionPay/Douyin)
- Extracts: counterparty (交易方), transaction time, payment method, account, amount
- Outputs to Excel with image path references
- SQLite-based deduplication for incremental runs
- Supports one-time scan and continuous file watching modes

## Tech Stack
- **Language**: Python 3.12+
- **AI Vision**: Qwen-VL (`qwen-vl-max`) via DashScope OpenAI-compatible API
- **Image processing**: Pillow (resize + compress before sending to API)
- **Excel**: openpyxl
- **Config**: YAML
- **File watching**: watchdog
- **State tracking**: SQLite (Python stdlib, no extra install)

## Project Structure

```
vibeCODING/
├── CLAUDE.md                    # This file — project docs for AI-assisted development
├── config.yaml                  # All config: paths, API keys, output, AI params
├── prompt.txt                   # AI vision prompt (Chinese, editable without touching code)
├── main.py                      # CLI entry point
├── requirements.txt
│
├── scanner/file_scanner.py      # Enumerate image files from configured paths
├── decoder/dat_decoder.py       # XOR-decrypt WeChat .dat files → plain images
├── ai_client/
│   ├── base.py                  # Abstract AI backend
│   └── qwen_client.py           # Qwen-VL via DashScope (OpenAI-compatible)
├── parser/transaction_parser.py # Parse AI JSON response → structured dict
├── writer/excel_writer.py       # Create/append Excel with 6 columns
├── core/
│   ├── pipeline.py              # Orchestration: scan→decode→classify→parse→write
│   ├── deduplicator.py          # SQLite dedup by (path, size, mtime)
│   └── watcher.py               # watchdog-based real-time file monitoring
└── utils/
    ├── config_loader.py         # YAML → dict with defaults, env var override, path resolution
    └── logger.py                # Structured logging to console + file
```

## Configuration

All settings in `config.yaml`. Key sections:

### wechat
- `scan_paths`: list of directories to scan (manual, no auto-discovery)
- `file_extensions`: [".dat", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]
- `min_file_size_kb` / `max_file_size_mb`: file size filters

### ai
- `base_url`: DashScope endpoint (default: `https://dashscope.aliyuncs.com/compatible-mode/v1`)
- `api_key`: DashScope API key (also read from `DASHSCOPE_API_KEY` env var)
- `model`: `qwen-vl-max`
- `prompt_file`: path to AI prompt text file (default: `./prompt.txt`)
- `image_max_side`: resize images before API call (default: 1568px)
- `image_quality`: JPEG compression quality (default: 85)

### output
- `excel_path`: output Excel file
- `columns`: [交易方, 交易时间, 支付方式, 账号, 交易金额, 对应图片]
- `decoded_images_dir`: where decoded .dat images are saved

## Usage

```bash
# Install dependencies
pip install -r requirements.txt

# Edit config.yaml — set API key and WeChat paths

# Test AI connectivity
python main.py --test-ai

# One-time scan
python main.py --mode once

# One-time scan with force re-processing
python main.py --mode once --force

# Continuous file watching
python main.py --mode watch
```

## Data Flow

```
Configured WeChat dirs (config.yaml)
  → file_scanner: enumerate .dat/.jpg/.png etc.
    → deduplicator: check SQLite (path, size, mtime)
      → dat_decoder: XOR decrypt .dat → temp .jpg
        → qwen_client: resize, base64, POST to DashScope with prompt.txt
          → transaction_parser: extract JSON or detect NOT_TRANSACTION
            → excel_writer: append row to Excel
```

## Design Decisions

1. **AI backend**: Single provider (Qwen-VL), but abstract base class (`ai_client/base.py`) makes switching easy
2. **Prompt in separate file**: `prompt.txt` is plain text, editable without touching Python code
3. **One-shot AI prompt**: single API call does both classification + extraction (saves cost/latency)
4. **Image pre-processing**: resize to max 1568px, JPEG Q85 before API call (reduces token cost)
5. **Dedup by (path, size, mtime)**: simple, robust, no file hashing needed
6. **Batch Excel writes**: in `once` mode, all results written at end; in `watch` mode, append per file
7. **No auto-discovery**: WeChat paths must be configured manually in config.yaml
8. **XOR-only .dat decryption**: covers WeChat v3.x; v4.0+ AES files are logged and skipped

## Dependencies

```
Pillow>=10.0.0       # Image processing
openpyxl>=3.1.0      # Excel I/O
requests>=2.31.0     # HTTP/AI API calls
PyYAML>=6.0          # Config parsing
watchdog>=4.0.0      # Optional: real-time file monitoring
```

SQLite is Python stdlib — no install needed.
