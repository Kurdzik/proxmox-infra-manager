import os
import base64
import hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derives a 32-byte key from the password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600_000,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_str(plaintext: str) -> str:
    """Encrypts a plaintext string (reversible encryption for API keys, tokens, etc.)"""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY environment variable not set.")

    salt = os.urandom(16)
    nonce = os.urandom(12)
    key = _derive_key(secret, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    packed_data = salt + nonce + ciphertext
    return base64.urlsafe_b64encode(packed_data).decode("utf-8")


def decrypt_str(encrypted_token: str) -> str:
    """Decrypts an encrypted string."""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY environment variable not set.")

    try:
        data = base64.urlsafe_b64decode(encrypted_token)
        salt = data[:16]
        nonce = data[16:28]
        ciphertext = data[28:]
        key = _derive_key(secret, salt)
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception as e:
        raise ValueError("Decryption failed. Invalid Key or Data Tampered.") from e


def hash_password(password: str) -> str:
    """One-way PBKDF2-HMAC-SHA256 hash for user passwords. Not reversible."""
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY environment variable not set.")

    salt = os.urandom(16)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    password_with_secret = f"{password}{secret}"
    password_hash = kdf.derive(password_with_secret.encode("utf-8"))
    packed_data = salt + password_hash
    return base64.urlsafe_b64encode(packed_data).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        raise ValueError("SECRET_KEY environment variable not set.")

    try:
        data = base64.urlsafe_b64decode(hashed_password)
        salt = data[:16]
        stored_hash = data[16:]
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
        password_with_secret = f"{password}{secret}"
        password_hash = kdf.derive(password_with_secret.encode("utf-8"))
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(password_hash, stored_hash)
    except Exception:
        return False
