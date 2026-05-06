import logging
import tempfile
from pathlib import Path
from typing import Optional, Tuple
import hashlib

logger = logging.getLogger("tx_scanner.decoder")

# Known image file signatures (magic bytes)
SIGNATURES = {
    b'\xff\xd8\xff': ('.jpg', 3),       # JPEG: FF D8 FF
    b'\x89PNG':       ('.png', 4),       # PNG: 89 50 4E 47
    b'GIF8':          ('.gif', 4),       # GIF: 47 49 46 38
    b'BM':            ('.bmp', 2),       # BMP: 42 4D
    b'RIFF':          ('.webp', 4),      # WEBP: 52 49 46 46
}


def _detect_xor_key_and_format(first_bytes: bytes) -> Optional[Tuple[int, str]]:
    """Try to find XOR key by testing against known image signatures."""
    for sig, (ext, sig_len) in SIGNATURES.items():
        candidate_key = first_bytes[0] ^ sig[0]
        match = True
        for i in range(1, sig_len):
            if i >= len(first_bytes):
                break
            if (first_bytes[i] ^ candidate_key) != sig[i]:
                match = False
                break
        if match:
            return candidate_key, ext
    return None


def _xor_decode(data: bytes, key: int) -> bytes:
    return bytes(b ^ key for b in data)


def decode_dat_file(dat_path: Path, decoded_dir: Path) -> Optional[Path]:
    """
    Attempt to XOR-decrypt a WeChat .dat file.
    Returns path to decoded image, or None if decryption fails.
    """
    try:
        with open(dat_path, 'rb') as f:
            raw = f.read()
    except OSError as e:
        logger.error("Cannot read %s: %s", dat_path.name, e)
        return None

    if len(raw) < 4:
        logger.warning("File too small: %s (%d bytes)", dat_path.name, len(raw))
        return None

    result = _detect_xor_key_and_format(raw[:8])
    if result is None:
        logger.debug("No XOR key found for: %s", dat_path.name)
        return None

    xor_key, ext = result
    logger.info("Decoded %s -> key=0x%02X format=%s", dat_path.name, xor_key, ext)

    decoded_data = _xor_decode(raw, xor_key)

    # Generate unique output filename
    file_hash = hashlib.sha256(raw).hexdigest()[:12]
    out_path = decoded_dir / f"{dat_path.stem}_{file_hash}{ext}"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, 'wb') as f:
        f.write(decoded_data)

    return out_path


def is_dat_encrypted(file_path: Path) -> bool:
    """Quick check if a .dat file appears to be encrypted (vs plain image)."""
    if file_path.suffix.lower() != '.dat':
        return False
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
    except OSError:
        return False

    # If the file starts with a known image signature, it's not encrypted
    for sig, (_, sig_len) in SIGNATURES.items():
        if header[:sig_len] == sig:
            return False

    # If XOR key exists, it's encrypted
    return _detect_xor_key_and_format(header) is not None
