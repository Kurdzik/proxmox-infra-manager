from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_

from src.models import ApiResponse, DNSEntry, UserInfo, AddDNSEntryRequest
from src.utils import get_db_session, get_user_info
from src.logger import get_logger, tenant_context

logger = get_logger(__name__)
router = APIRouter(prefix="/dns", tags=["DNS Management"])


@router.get("/entries", response_model=ApiResponse)
def list_entries(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.dns"):
        entries = db_session.exec(
            select(DNSEntry).where(DNSEntry.tenant_id == user_info.tenant_id)
        ).all()
        return ApiResponse(message="DNS entries retrieved", data={"entries": [e.model_dump() for e in entries]})


@router.post("/entries", response_model=ApiResponse)
def add_entry(
    request: AddDNSEntryRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.dns"):
        entry = DNSEntry(tenant_id=user_info.tenant_id, **request.model_dump())
        db_session.add(entry)
        db_session.commit()
        db_session.refresh(entry)

        from src.services.worker import sync_dns_entry
        sync_dns_entry.apply_async(
            kwargs={"entry_id": entry.id, "tenant_id": user_info.tenant_id},
            ignore_result=True,
        )

        return ApiResponse(message="DNS entry created", data={"id": entry.id})


@router.delete("/entries/{entry_id}", response_model=ApiResponse)
def delete_entry(
    entry_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.dns"):
        entry = db_session.exec(
            select(DNSEntry).where(
                and_(DNSEntry.tenant_id == user_info.tenant_id, DNSEntry.id == entry_id)
            )
        ).first()
        if not entry:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNS entry not found")

        db_session.delete(entry)
        db_session.commit()
        return ApiResponse(message="DNS entry deleted")


@router.post("/sync", response_model=ApiResponse)
def sync_all(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    from src.services.worker import sync_all_dns
    sync_all_dns.apply_async(kwargs={"tenant_id": user_info.tenant_id}, ignore_result=True)
    return ApiResponse(message="DNS sync queued")
