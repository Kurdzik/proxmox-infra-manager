from pydantic import BaseModel


class ProxmoxCredentials(BaseModel):
    url: str            # https://pve01.internal:8006
    token_id: str       # e.g. root@pam!infra-manager
    token_secret: str   # decrypted at use time, never stored plaintext
    verify_ssl: bool = False
