from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


def generate_ed25519_keypair() -> tuple[str, str]:
    """Generate an Ed25519 SSH keypair.

    Returns:
        (public_key_openssh, private_key_openssh_pem) — both as UTF-8 strings.
        The private key is in OpenSSH PEM format, compatible with asyncssh.import_private_key().
    """
    private_key = Ed25519PrivateKey.generate()

    public_key_str = private_key.public_key().public_bytes(
        Encoding.OpenSSH, PublicFormat.OpenSSH
    ).decode("utf-8")

    private_key_str = private_key.private_bytes(
        Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()
    ).decode("utf-8")

    return public_key_str, private_key_str
