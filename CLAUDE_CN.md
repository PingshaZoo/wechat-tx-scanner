# 微信交易图片识别系统

## 概述
基于 Windows 的系统，扫描本地微信文件存储中的图片，使用 AI 视觉（通义千问 VL，通过 DashScope）识别交易相关图片，提取结构化交易数据，并将结果写入 Excel。

## 核心功能
- 扫描微信 `FileStorage/Image/`、`FileStorage/File/`、`FileStorage/MsgAttach/` 目录
- XOR 解密微信 `.dat` 加密图片文件（覆盖微信 v3.x；v4.0+ AES 文件跳过不处理）
- AI 视觉分类：识别收据、发票、转账截图（微信/支付宝/银行/云闪付/抖音）
- 提取：交易方、交易时间、支付方式、账号、交易金额
- 输出到 Excel，包含图片路径引用
- 基于 SQLite 的去重机制，支持增量扫描
- 支持一次性扫描和持续文件监控两种模式

## 技术栈
- **语言**：Python 3.12+
- **AI 视觉**：通义千问 VL（`qwen-vl-max`），通过 DashScope OpenAI 兼容 API
- **图片处理**：Pillow（发送 API 前缩放和压缩图片）
- **Excel**：openpyxl
- **配置**：YAML
- **文件监控**：watchdog
- **状态追踪**：SQLite（Python 标准库，无需额外安装）

## 项目结构

```
vibeCODING/
├── CLAUDE.md                    # 本文件 — 用于 AI 辅助开发的项目文档
├── config.yaml                  # 所有配置：路径、API 密钥、输出、AI 参数
├── prompt.txt                   # AI 视觉提示词（中文，无需改代码即可编辑）
├── main.py                      # CLI 入口
├── requirements.txt
│
├── scanner/file_scanner.py      # 从配置路径枚举图片文件
├── decoder/dat_decoder.py       # XOR 解密微信 .dat 文件 → 原始图片
├── ai_client/
│   ├── base.py                  # 抽象 AI 后端基类
│   └── qwen_client.py           # 通义千问 VL，通过 DashScope（OpenAI 兼容）
├── parser/transaction_parser.py # 解析 AI JSON 响应 → 结构化字典
├── writer/excel_writer.py       # 创建/追加 Excel（6 列）
├── core/
│   ├── pipeline.py              # 编排：扫描→解密→分类→解析→写入
│   ├── deduplicator.py          # 基于 (路径, 大小, 修改时间) 的 SQLite 去重
│   └── watcher.py               # 基于 watchdog 的实时文件监控
└── utils/
    ├── config_loader.py         # YAML → 字典，含默认值、环境变量覆盖、路径解析
    └── logger.py                # 结构化日志（控制台 + 文件）
```

## 配置说明

所有设置位于 `config.yaml`。主要配置项：

### wechat（微信）
- `scan_paths`：要扫描的目录列表（手动配置，不自动发现）
- `file_extensions`：`[".dat", ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp"]`
- `min_file_size_kb` / `max_file_size_mb`：文件大小过滤

### ai（AI 相关）
- `base_url`：DashScope 端点（默认：`https://dashscope.aliyuncs.com/compatible-mode/v1`）
- `api_key`：DashScope API 密钥（也可通过环境变量 `DASHSCOPE_API_KEY` 读取）
- `model`：`qwen-vl-max`
- `prompt_file`：AI 提示词文本文件路径（默认：`./prompt.txt`）
- `image_max_side`：发往 API 前图片最大边长（默认：1568px）
- `image_quality`：JPEG 压缩质量（默认：85）

### output（输出）
- `excel_path`：输出 Excel 文件路径
- `columns`：`[交易方, 交易时间, 支付方式, 账号, 交易金额, 对应图片]`
- `decoded_images_dir`：解密后的 .dat 图片存放目录

## 使用方法

```bash
# 安装依赖
pip install -r requirements.txt

# 编辑 config.yaml — 设置 API 密钥和微信路径

# 测试 AI 连通性
python main.py --test-ai

# 一次性扫描
python main.py --mode once

# 一次性扫描（强制重新处理全部文件）
python main.py --mode once --force

# 持续文件监控
python main.py --mode watch
```

## 数据流程

```
配置的微信目录（config.yaml）
  → file_scanner：枚举 .dat/.jpg/.png 等文件
    → deduplicator：查 SQLite（路径, 大小, 修改时间）
      → dat_decoder：XOR 解密 .dat → 临时 .jpg
        → qwen_client：缩放、base64、带 prompt.txt 发 POST 到 DashScope
          → transaction_parser：提取 JSON 或检测到 NOT_TRANSACTION
            → excel_writer：追加一行到 Excel
```

## 设计决策

1. **AI 后端**：单一供应商（通义千问 VL），但抽象基类（`ai_client/base.py`）便于切换
2. **提示词独立文件**：`prompt.txt` 为纯文本，无需改动 Python 代码即可编辑
3. **单次 AI 提示**：一次 API 调用同时完成分类和提取（节省成本和延迟）
4. **图片预处理**：API 调用前缩放到最大 1568px、JPEG Q85（降低 token 消耗）
5. **基于 (路径, 大小, 修改时间) 的去重**：简单可靠，无需文件哈希
6. **批量 Excel 写入**：`once` 模式下所有结果一次性写入；`watch` 模式下每文件追加
7. **不自动发现**：微信路径必须在 config.yaml 中手动配置
8. **仅 XOR 解密 .dat**：覆盖微信 v3.x；v4.0+ AES 文件记录日志后跳过

## 依赖

```
Pillow>=10.0.0       # 图片处理
openpyxl>=3.1.0      # Excel 读写
requests>=2.31.0     # HTTP/AI API 调用
PyYAML>=6.0          # 配置解析
watchdog>=4.0.0      # 可选：实时文件监控
```

SQLite 是 Python 标准库 — 无需额外安装。
