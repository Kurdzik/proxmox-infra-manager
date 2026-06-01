from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, and_, select

from src.crypto import decrypt_str, encrypt_str
from src.models import ApiResponse, UserInfo, UserSSHKey
from src.services.ssh_service import generate_ed25519_keypair
from src.utils import get_db_session, get_user_info
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/keys", tags=["SSH Keys"])


@router.get("/list", response_model=ApiResponse)
def list_keys(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    keys = db_session.exec(
        select(UserSSHKey).where(
            and_(UserSSHKey.tenant_id == user_info.tenant_id, UserSSHKey.user_id == user_info.user_id)
        )
    ).all()
    return ApiResponse(
        message="SSH keys retrieved",
        data={
            "keys": [
                {
                    "id": k.id,
                    "name": k.name,
                    "public_key": k.public_key,
                    "has_private_key": bool(k.private_key_encrypted),
                    "created_at": k.created_at.isoformat(),
                }
                for k in keys
            ]
        },
    )


@router.post("/generate", response_model=ApiResponse)
def generate_key(
    request: dict,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    name = (request.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name is required")

    public_key, private_key_pem = generate_ed25519_keypair()
    key = UserSSHKey(
        user_id=user_info.user_id,
        tenant_id=user_info.tenant_id,
        name=name,
        public_key=public_key,
        private_key_encrypted=encrypt_str(private_key_pem),
        created_at=datetime.now(),
    )
    db_session.add(key)
    db_session.commit()
    db_session.refresh(key)

    logger.info("user_ssh_key_generated", key_id=key.id, name=name)
    return ApiResponse(
        message="SSH keypair generated",
        data={
            "id": key.id,
            "name": key.name,
            "public_key": key.public_key,
            "private_key_pem": private_key_pem,  # returned once — not stored in plain text
        },
    )


@router.post("/import", response_model=ApiResponse)
def import_key(
    request: dict,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    name = (request.get("name") or "").strip()
    public_key = (request.get("public_key") or "").strip()
    if not name or not public_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="name and public_key are required")
    if not public_key.startswith("ssh-"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="public_key must be an OpenSSH public key (starting with ssh-)",
        )

    key = UserSSHKey(
        user_id=user_info.user_id,
        tenant_id=user_info.tenant_id,
        name=name,
        public_key=public_key,
        private_key_encrypted=None,
        created_at=datetime.now(),
    )
    db_session.add(key)
    db_session.commit()
    db_session.refresh(key)

    logger.info("user_ssh_key_imported", key_id=key.id, name=name)
    return ApiResponse(message="SSH public key imported", data={"id": key.id, "name": key.name})


@router.get("/{key_id}/private", response_model=ApiResponse)
def download_private_key(
    key_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    key = db_session.exec(
        select(UserSSHKey).where(
            and_(
                UserSSHKey.id == key_id,
                UserSSHKey.user_id == user_info.user_id,
                UserSSHKey.tenant_id == user_info.tenant_id,
            )
        )
    ).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSH key not found")
    if not key.private_key_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This key was imported — no private key stored",
        )
    private_key_pem = decrypt_str(key.private_key_encrypted)
    return ApiResponse(message="Private key retrieved", data={"private_key_pem": private_key_pem, "name": key.name})


@router.delete("/{key_id}", response_model=ApiResponse)
def delete_key(
    key_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    key = db_session.exec(
        select(UserSSHKey).where(
            and_(
                UserSSHKey.id == key_id,
                UserSSHKey.user_id == user_info.user_id,
                UserSSHKey.tenant_id == user_info.tenant_id,
            )
        )
    ).first()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SSH key not found")
    db_session.delete(key)
    db_session.commit()
    logger.info("user_ssh_key_deleted", key_id=key_id)
    return ApiResponse(message="SSH key deleted")
