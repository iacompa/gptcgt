import base64
import logging
import os

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from api.config import settings

logger = logging.getLogger(__name__)


def _get_key() -> bytes:
    key_hex = settings.encryption_key
    if not key_hex or len(key_hex) != 64:
        raise ValueError("ENCRYPTION_KEY must be a 64-character hex string (32 bytes)")
    try:
        return bytes.fromhex(key_hex)
    except ValueError:
        raise ValueError("Invalid ENCRYPTION_KEY format (must be valid hex)")


def encrypt_key(plain_text: str) -> str:
    """Encrypts a string using AES-256-GCM. Returns base64 encoded ciphertext."""
    iv = os.urandom(12)
    key = _get_key()
    encryptor = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend()).encryptor()

    ciphertext = encryptor.update(plain_text.encode()) + encryptor.finalize()

    # Store IV + Ciphertext + Tag together
    payload = iv + ciphertext + encryptor.tag
    return base64.b64encode(payload).decode()


def decrypt_key(encrypted_str: str) -> str:
    """Decrypts a base64 encoded AES-256-GCM string."""
    try:
        payload = base64.b64decode(encrypted_str)
        iv = payload[:12]
        tag = payload[-16:]
        ciphertext = payload[12:-16]

        key = _get_key()
        decryptor = Cipher(
            algorithms.AES(key), modes.GCM(iv, tag), backend=default_backend()
        ).decryptor()

        plain_text = decryptor.update(ciphertext) + decryptor.finalize()
        return plain_text.decode()
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
