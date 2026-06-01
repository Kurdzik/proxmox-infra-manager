import asyncio
import json
from datetime import datetime
from urllib.parse import urlparse

import asyncssh
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlmodel import Session, and_, select

from src.crypto import decrypt_str
from src.logger import get_logger
from src.middleware import engine
from src.models import PlatformConfig, Session as UserSession, User, VM, VMSSHKey

logger = get_logger(__name__)
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
        if not vm.vmid or vm.vmid == 0:
            await websocket.close(code=4004, reason="VM has no Proxmox ID — still provisioning?")
            return
        if vm.status != "running":
            await websocket.send_text(
                f"\r\n\x1b[31mVM is not running (status: {vm.status})\x1b[0m\r\n"
            )
            await websocket.close(code=4004, reason="VM not running")
            return
        if not vm.ip_address:
            await websocket.send_text(
                "\r\n\x1b[31mVM has no IP address yet — wait for provisioning to complete.\x1b[0m\r\n"
            )
            await websocket.close(code=4004, reason="VM has no IP address")
            return

        vm_key = db.exec(
            select(VMSSHKey).where(VMSSHKey.vm_id == vm_id)
        ).first()
        if not vm_key:
            await websocket.send_text(
                "\r\n\x1b[31mNo SSH key found for this VM — terminal unavailable.\x1b[0m\r\n"
            )
            await websocket.close(code=4004, reason="No SSH key")
            return

        config = db.exec(select(PlatformConfig)).first()
        if not config or not config.is_initialized:
            await websocket.close(code=4500, reason="Platform not initialized")
            return
        if not config.ssh_username or not config.encrypted_ssh_password:
            await websocket.send_text(
                "\r\n\x1b[31mProxmox SSH credentials not configured — go to Settings.\x1b[0m\r\n"
            )
            await websocket.close(code=4500, reason="SSH credentials not configured")
            return

        proxmox_host = urlparse(config.proxmox_url).hostname
        ssh_user = config.ssh_username
        ssh_password = decrypt_str(config.encrypted_ssh_password)
        vm_ip = vm.ip_address
        vm_user = vm.cloud_init_user or "ubuntu"
        vm_privkey_pem = decrypt_str(vm_key.private_key_encrypted)

    # Wait for the initial resize message the frontend sends in ws.onopen.
    # This gives us the real terminal dimensions before creating the SSH process,
    # preventing cursor-positioning artifacts from a size mismatch.
    initial_cols, initial_rows = 80, 24
    try:
        first_msg_raw = await asyncio.wait_for(websocket.receive_text(), timeout=3.0)
        first_msg = json.loads(first_msg_raw)
        if first_msg.get("type") == "resize":
            initial_cols = int(first_msg.get("cols", 80))
            initial_rows = int(first_msg.get("rows", 24))
    except (asyncio.TimeoutError, Exception):
        pass  # fall back to 80×24

    logger.info(
        "terminal_ssh_connecting",
        vm_id=vm_id,
        proxmox_host=proxmox_host,
        vm_ip=vm_ip,
        vm_user=vm_user,
        cols=initial_cols,
        rows=initial_rows,
    )

    try:
        async with asyncssh.connect(
            proxmox_host,
            username=ssh_user,
            password=ssh_password,
            known_hosts=None,
        ) as jump:
            vm_key_obj = asyncssh.import_private_key(vm_privkey_pem)
            async with asyncssh.connect(
                vm_ip,
                username=vm_user,
                client_keys=[vm_key_obj],
                known_hosts=None,
                tunnel=jump,
            ) as vm_conn:
                logger.info("terminal_ssh_connected", vm_id=vm_id, vm_ip=vm_ip)

                process = await vm_conn.create_process(
                    term_type="xterm-256color",
                    term_size=(initial_cols, initial_rows),
                )

                stop = asyncio.Event()

                async def ws_to_ssh():
                    try:
                        async for msg in websocket.iter_text():
                            if stop.is_set():
                                break
                            try:
                                parsed = json.loads(msg)
                                msg_type = parsed.get("type")
                                if msg_type == "resize":
                                    cols = int(parsed.get("cols", 80))
                                    rows = int(parsed.get("rows", 24))
                                    process.change_terminal_size(cols, rows)
                                elif msg_type == "data":
                                    process.stdin.write(parsed.get("data", ""))
                                else:
                                    # Unknown JSON message — pass data field through if present
                                    text = parsed.get("data", "")
                                    if text:
                                        process.stdin.write(text)
                            except (json.JSONDecodeError, KeyError):
                                process.stdin.write(msg)
                    except (WebSocketDisconnect, Exception) as e:
                        logger.info("ws_to_ssh_ended", reason=type(e).__name__)
                    finally:
                        stop.set()
                        try:
                            process.stdin.write_eof()
                        except Exception:
                            pass

                async def ssh_to_ws():
                    # Use read(n) instead of "async for" iteration — the iterator
                    # waits for newlines, causing typed characters to be invisible
                    # until Enter is pressed. read(n) returns as soon as any data
                    # arrives (up to n chars), giving real-time echo.
                    try:
                        while not stop.is_set():
                            chunk = await process.stdout.read(4096)
                            if not chunk:  # EOF — remote shell exited
                                break
                            await websocket.send_text(chunk)
                    except Exception as e:
                        logger.info("ssh_to_ws_ended", reason=type(e).__name__)
                    finally:
                        stop.set()

                await asyncio.gather(ws_to_ssh(), ssh_to_ws(), return_exceptions=True)

    except asyncssh.PermissionDenied as e:
        logger.warning("terminal_ssh_auth_failed", vm_id=vm_id, error=str(e))
        try:
            await websocket.send_text(
                f"\r\n\x1b[31mSSH authentication failed to VM {vm_ip}.\x1b[0m\r\n"
                "\x1b[33mThe VM may still be starting up — try again in a moment.\x1b[0m\r\n"
            )
        except Exception:
            pass
    except asyncssh.DisconnectError as e:
        logger.info("terminal_ssh_disconnected", vm_id=vm_id, reason=str(e))
    except (WebSocketDisconnect, Exception) as e:
        logger.error("terminal_error", vm_id=vm_id, error=str(e), exc_info=True)
        try:
            await websocket.send_text(
                f"\r\n\x1b[31mConnection error: {type(e).__name__}: {e}\x1b[0m\r\n"
            )
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
