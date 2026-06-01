import asyncio
import json
from datetime import datetime

import asyncssh
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session, and_, select

from src.crypto import decrypt_str
from src.middleware import engine
from src.models import Session as UserSession, User, VM, VMSSHKey

router = APIRouter(prefix="/vms", tags=["Terminal"])


@router.websocket("/{vm_id}/terminal")
async def vm_terminal(
    websocket: WebSocket,
    vm_id: int,
    token: str = Query(...),
):
    await websocket.accept()

    with Session(engine) as db:
        # Validate session token manually — middleware does not run on WebSocket paths
        user_session = db.exec(
            select(UserSession).where(UserSession.token == token)
        ).first()
        if not user_session or user_session.expires_at < datetime.now():
            await websocket.close(code=4001, reason="Unauthorized")
            return

        user = db.get(User, user_session.user_id)
        if not user or not user.is_active:
            await websocket.close(code=4001, reason="Unauthorized")
            return

        vm = db.exec(
            select(VM).where(and_(VM.tenant_id == user.tenant_id, VM.id == vm_id))
        ).first()
        if not vm:
            await websocket.close(code=4004, reason="VM not found")
            return
        if not vm.ip_address:
            await websocket.close(code=4004, reason="VM has no IP address — still provisioning?")
            return

        ssh_key = db.exec(
            select(VMSSHKey).where(
                and_(VMSSHKey.tenant_id == user.tenant_id, VMSSHKey.vm_id == vm_id)
            )
        ).first()
        if not ssh_key:
            await websocket.close(code=4004, reason="No SSH key found for this VM")
            return

        private_key_pem = decrypt_str(ssh_key.private_key_encrypted)
        username = vm.cloud_init_user or "ubuntu"
        ip_address = vm.ip_address

    try:
        private_key = asyncssh.import_private_key(private_key_pem)

        async with await asyncssh.connect(
            ip_address,
            username=username,
            client_keys=[private_key],
            known_hosts=None,  # skip host-key verification for managed VMs
        ) as conn:
            process = await conn.create_process(term_type="xterm-256color")

            async def ws_to_ssh():
                try:
                    async for msg in websocket.iter_text():
                        try:
                            data = json.loads(msg)
                            if data.get("type") == "resize":
                                cols = int(data.get("cols", 80))
                                rows = int(data.get("rows", 24))
                                process.change_terminal_size(cols, rows)
                            else:
                                process.stdin.write(data.get("data", ""))
                        except (json.JSONDecodeError, KeyError, ValueError):
                            # Raw text fallback (data not JSON-framed)
                            process.stdin.write(msg)
                except WebSocketDisconnect:
                    pass

            async def ssh_to_ws():
                try:
                    async for data in process.stdout:
                        await websocket.send_text(data)
                except (asyncssh.DisconnectError, WebSocketDisconnect):
                    pass

            await asyncio.gather(ws_to_ssh(), ssh_to_ws())

    except WebSocketDisconnect:
        pass
    except asyncssh.Error as e:
        try:
            await websocket.send_text(f"\r\n\x1b[31mSSH error: {e}\x1b[0m\r\n")
            await websocket.close(code=4500, reason=str(e))
        except Exception:
            pass
    except Exception as e:
        try:
            await websocket.send_text(f"\r\n\x1b[31mConnection error: {e}\x1b[0m\r\n")
            await websocket.close(code=4500, reason=str(e))
        except Exception:
            pass
