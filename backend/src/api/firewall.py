from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, and_

from src.models import ApiResponse, FirewallRule, UserInfo, AddFirewallRuleRequest
from src.utils import get_db_session, get_user_info
from src.logger import get_logger, tenant_context

logger = get_logger(__name__)
router = APIRouter(prefix="/firewall", tags=["Firewall Management"])


@router.get("/rules", response_model=ApiResponse)
def list_rules(
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.firewall"):
        rules = db_session.exec(
            select(FirewallRule).where(FirewallRule.tenant_id == user_info.tenant_id)
        ).all()
        return ApiResponse(message="Rules retrieved", data={"rules": [r.model_dump() for r in rules]})


@router.post("/rules", response_model=ApiResponse)
def add_rule(
    request: AddFirewallRuleRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.firewall"):
        rule = FirewallRule(tenant_id=user_info.tenant_id, **request.model_dump())
        db_session.add(rule)
        db_session.commit()
        db_session.refresh(rule)

        from src.services.worker import sync_firewall_rule
        sync_firewall_rule.apply_async(
            kwargs={"rule_id": rule.id, "tenant_id": user_info.tenant_id},
            ignore_result=True,
        )

        return ApiResponse(message="Firewall rule added", data={"id": rule.id})


@router.put("/rules/{rule_id}", response_model=ApiResponse)
def update_rule(
    rule_id: int,
    request: AddFirewallRuleRequest,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.firewall"):
        rule = db_session.exec(
            select(FirewallRule).where(
                and_(FirewallRule.tenant_id == user_info.tenant_id, FirewallRule.id == rule_id)
            )
        ).first()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

        for k, v in request.model_dump().items():
            setattr(rule, k, v)
        rule.proxmox_synced = False
        db_session.add(rule)
        db_session.commit()

        from src.services.worker import sync_firewall_rule
        sync_firewall_rule.apply_async(
            kwargs={"rule_id": rule_id, "tenant_id": user_info.tenant_id},
            ignore_result=True,
        )

        return ApiResponse(message="Firewall rule updated")


@router.delete("/rules/{rule_id}", response_model=ApiResponse)
def delete_rule(
    rule_id: int,
    db_session: Session = Depends(get_db_session),
    user_info: UserInfo = Depends(get_user_info),
):
    with tenant_context(tenant_id=user_info.tenant_id, service_name="api.firewall"):
        rule = db_session.exec(
            select(FirewallRule).where(
                and_(FirewallRule.tenant_id == user_info.tenant_id, FirewallRule.id == rule_id)
            )
        ).first()
        if not rule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")

        db_session.delete(rule)
        db_session.commit()
        return ApiResponse(message="Firewall rule deleted")
