import os
from pathlib import Path
import yaml


DEFAULT_CONFIG = {
    "wechat": {
        "scan_paths": [],
        "file_extensions": [".dat", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"],
        "min_file_size_kb": 5,
        "max_file_size_mb": 20,
    },
    "ai": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "",
        "model": "qwen-vl-max",
        "max_tokens": 1024,
        "temperature": 0.1,
        "timeout_seconds": 60,
        "max_retries": 3,
        "image_max_side": 1568,
        "image_quality": 85,
        "prompt_file": "./prompt.txt",
    },
    "output": {
        "excel_path": "./transaction_records.xlsx",
        "sheet_name": "交易记录",
        "columns": ["交易方", "交易时间", "支付方式", "账号", "交易金额", "对应图片"],
        "decoded_images_dir": "./decoded_images",
    },
    "state": {
        "db_path": "./processed.db",
    },
    "logging": {
        "level": "INFO",
        "file": "./app.log",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(config_path: str = "config.yaml") -> dict:
    config = DEFAULT_CONFIG.copy()
    path = Path(config_path)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, user_config)

    # Resolve API key from env var if not set in file
    if not config["ai"].get("api_key"):
        config["ai"]["api_key"] = os.environ.get("DASHSCOPE_API_KEY", "")

    # Resolve relative paths against config file directory
    base_dir = path.parent.resolve()
    for section, key in [("output", "excel_path"), ("output", "decoded_images_dir"),
                         ("state", "db_path"), ("logging", "file"),
                         ("ai", "prompt_file")]:
        p = Path(config[section][key])
        if not p.is_absolute():
            config[section][key] = str(base_dir / p)

    return config
