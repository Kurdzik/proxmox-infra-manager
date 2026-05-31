import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from src.models import ApiResponse, AllowedImage, UserInfo, AddAllowedImageRequest
from src.plugin_manager import IntegrationClient
from src.utils import get_db_session, get_user_info, require_admin
from src.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/images", tags=["Image Allowlist"])


@router.get("/list", response_model=ApiResponse)
def list_allowed_images(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    """Returns merged allowlist: plugin-sourced images + platform-local overrides."""
    client = IntegrationClient(db_session)
    plugin_images = client.get_allowed_images()

    local_images = db_session.exec(select(AllowedImage)).all()
    local_as_dicts = [
        {
            "name": img.image_name,
            "tags": json.loads(img.allowed_tags) if img.allowed_tags else [],
            "description": img.description,
            "source": "platform",
        }
        for img in local_images
    ]

    for img in plugin_images:
        img["source"] = "plugin"

    return ApiResponse(
        message="Allowed images retrieved",
        data={"images": plugin_images + local_as_dicts},
    )


@router.post("/add", response_model=ApiResponse)
def add_allowed_image(
    request: AddAllowedImageRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    require_admin(user_info)

    image = AllowedImage(
        image_name=request.image_name,
        tag_policy=request.tag_policy,
        allowed_tags=json.dumps(request.allowed_tags) if request.allowed_tags else None,
        description=request.description,
        added_by_tenant_id=user_info.tenant_id,
    )
    db_session.add(image)
    db_session.commit()
    db_session.refresh(image)
    return ApiResponse(message="Image added to allowlist", data={"id": image.id})


@router.delete("/{image_id}", response_model=ApiResponse)
def remove_allowed_image(
    image_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    require_admin(user_info)

    image = db_session.exec(select(AllowedImage).where(AllowedImage.id == image_id)).first()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    db_session.delete(image)
    db_session.commit()
    return ApiResponse(message="Image removed from allowlist")
