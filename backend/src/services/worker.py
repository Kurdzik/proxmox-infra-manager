import json
import os
import shutil
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine, text
from sqlmodel import Session, and_, select

from src import configure_logger, get_logger, tenant_context
from src.crypto import decrypt_str, encrypt_str
from src.models import (
    AllowedImage,
    DNSEntry,
    DockerService,
    FirewallRule,
    Logs,
    NginxConfig,
    PlatformConfig,
    Plugin,
    ProxmoxNode,
    TenantLogSettings,
    TenantVNet,
    TerraformWorkspace,
    VM,
    VMSSHKey,
    VMTemplate,
)
from src.nginx_manager import NginxConfigManager
from src.plugin_manager import DockerComposeRunner, IntegrationClient, PluginManifest
from src.proxmox import ProxmoxAdapterFactory, ProxmoxCredentials
from src.services.ssh_service import generate_ed25519_keypair
from src.terraform import TerraformManager

app = Celery("infra-manager-worker")
app.conf.update(
    broker_url=os.environ["CELERY_BROKER_URL"],
    result_backend=os.environ["CELERY_RESULT_BACKEND"],
    timezone="UTC",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3540,
    worker_hijack_root_logger=False,
    beat_scheduler="src.services.scheduler:DynamicScheduler",
)

DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
configure_logger(engine, service_name="worker")
logger = get_logger("worker")

TASK_MAX_RETRIES = 3
PROVISION_CONCURRENCY = 1


@contextmanager
def _tenant_provision_slot(tenant_id: str):
    lock_conn = engine.connect()
    try:
        lock_key = hash(f"infra-manager:provision:{tenant_id}") % (2**31)
        result = lock_conn.execute(text(f"SELECT pg_try_advisory_lock({lock_key})"))
        acquired = result.scalar()
        yield acquired
    finally:
        lock_conn.execute(text(f"SELECT pg_advisory_unlock_all()"))
        lock_conn.close()


def _get_adapter(db_session: Session):
    config = db_session.exec(select(PlatformConfig)).first()
    if not config or not config.is_initialized:
        raise RuntimeError("Platform not initialized")
    token_secret = decrypt_str(config.encrypted_token_secret)
    credentials = ProxmoxCredentials(
        url=config.proxmox_url,
        token_id=config.token_id,
        token_secret=token_secret,
        verify_ssl=config.verify_ssl,
    )
    return ProxmoxAdapterFactory.create(config.proxmox_version, credentials)




# ---------------------------------------------------------------------------
# Cluster sync
# ---------------------------------------------------------------------------

@app.task(bind=True, soft_time_limit=120, time_limit=180)
def sync_cluster_state(self):
    with Session(engine) as db:
        try:
            adapter = _get_adapter(db)
        except RuntimeError:
            return

        nodes = adapter.list_nodes()
        for node_data in nodes:
            node_name = node_data.get("node")

            status_data = {}
            try:
                status_data = adapter.get_node_status(node_name)
            except Exception:
                pass

            cpu_count = node_data.get("maxcpu") or status_data.get("cpuinfo", {}).get("cpus")
            cpu_usage = node_data.get("cpu") or status_data.get("cpu")
            memory_total = node_data.get("maxmem") or status_data.get("memory", {}).get("total")
            memory_used = node_data.get("mem") or status_data.get("memory", {}).get("used")
            uptime = node_data.get("uptime") or status_data.get("uptime")

            existing = db.exec(select(ProxmoxNode).where(ProxmoxNode.node_name == node_name)).first()
            if existing:
                existing.status = node_data.get("status", "unknown")
                existing.cpu_count = cpu_count
                existing.cpu_usage = cpu_usage
                existing.memory_total = memory_total
                existing.memory_used = memory_used
                existing.uptime = uptime
                existing.last_synced_at = datetime.now()
                db.add(existing)
            else:
                db.add(ProxmoxNode(
                    node_name=node_name,
                    status=node_data.get("status", "unknown"),
                    cpu_count=cpu_count,
                    cpu_usage=cpu_usage,
                    memory_total=memory_total,
                    memory_used=memory_used,
                    uptime=uptime,
                ))
        db.commit()

        for node_data in nodes:
            node_name = node_data.get("node")
            try:
                vms = adapter.list_vms(node_name)
                for vm_data in vms:
                    vmid = vm_data.get("vmid")
                    vm = db.exec(select(VM).where(VM.vmid == vmid)).first()
                    if vm:
                        # Don't overwrite managed transition states — the provision
                        # task owns "provisioning" until SSH is verified.
                        if vm.status != "provisioning":
                            vm.status = vm_data.get("status", "stopped")
                        if vm_data.get("cpus"):
                            vm.cpu_cores = vm_data["cpus"]
                        if vm_data.get("maxmem"):
                            vm.memory_mb = vm_data["maxmem"] // (1024 * 1024)
                        if vm_data.get("maxdisk"):
                            vm.disk_gb = vm_data["maxdisk"] // (1024 * 1024 * 1024)
                        if vm_data.get("status") == "running":
                            try:
                                ip = adapter.get_vm_ip(node_name, vmid)
                                if ip:
                                    vm.ip_address = ip
                            except Exception:
                                pass
                        vm.updated_at = datetime.now()
                        db.add(vm)
            except Exception as e:
                logger.warning("node_sync_failed", node=node_name, error=str(e))

        db.commit()


# ---------------------------------------------------------------------------
# VM provisioning (Terraform-based)
# ---------------------------------------------------------------------------

@app.task(bind=True, max_retries=TASK_MAX_RETRIES, soft_time_limit=3540, time_limit=3600)
def provision_vm(
    self,
    vm_id: int,
    node_name: str,
    vm_name: str,
    tenant_id: str,
    image_id: str,
    cpu_cores: int,
    memory_mb: int,
    disk_gb: int,
    cloud_init_user: str,
    bridge: str,
    user_ssh_key_ids: list = [],
):
    from celery.exceptions import Retry
    from src.images import IMAGE_BY_ID

    with tenant_context(tenant_id=tenant_id, service_name="worker.provision_vm"):
        work_dir = f"/tmp/tf_{vm_id}"
        vmid: Optional[int] = None
        provisioned_vmid: Optional[int] = None
        initial_ip: Optional[str] = None

        # ── Phase 0: Reserve VMID — advisory lock held for milliseconds only ─────────
        #
        # The lock serialises concurrent VMID allocations for the same tenant so two
        # simultaneous provisions don't pick the same vmid. It must be released BEFORE
        # terraform runs — terraform init + apply can take 5-20 minutes and holding
        # the lock that long causes MaxRetriesExceededError for any second provision.
        try:
            with Session(engine) as db:
                with _tenant_provision_slot(tenant_id) as acquired:
                    if not acquired:
                        raise self.retry(countdown=30)

                    vm = db.exec(select(VM).where(and_(VM.tenant_id == tenant_id, VM.id == vm_id))).first()
                    if not vm:
                        raise ValueError(f"VM record {vm_id} not found")

                    img = IMAGE_BY_ID.get(image_id)
                    if not img or img.get("image_type") != "cloud-image":
                        raise ValueError(f"Image '{image_id}' not found or is not a cloud-image type")

                    adapter = _get_adapter(db)
                    proxmox_vmids = {v.get("vmid") for v in adapter.list_vms(node_name)}
                    db_vmids = {v.vmid for v in db.exec(select(VM).where(VM.vmid > 0)).all()}
                    existing_vmids = proxmox_vmids | db_vmids
                    vmid = max(existing_vmids, default=99) + 1
                    vm.vmid = vmid
                    db.add(vm)
                    db.commit()
                # ← advisory lock released here; VMID is now reserved in DB
        except Retry:
            raise  # don't catch retries as errors
        except Exception as e:
            with Session(engine) as db:
                vm = db.exec(select(VM).where(VM.id == vm_id)).first()
                if vm:
                    vm.status = "error"
                    vm.updated_at = datetime.now()
                    db.add(vm)
                    db.commit()
            logger.error("vm_provision_failed", vm_id=vm_id, name=vm_name, error=str(e), exc_info=True, persist_db=True)
            raise

        # ── Phase 1: Terraform init + apply — no lock held ───────────────────────────
        #
        # Read all config values into locals so the DB session can be closed before
        # the long-running subprocess calls. Keeps connection pool usage minimal.
        try:
            with Session(engine) as db:
                config = db.exec(select(PlatformConfig)).first()
                token_secret = decrypt_str(config.encrypted_token_secret)
                api_token = f"{config.token_id}={token_secret}"
                if not config.ssh_username or not config.encrypted_ssh_password:
                    raise ValueError(
                        "SSH credentials not configured. Go to Settings → SSH Credentials and save Proxmox SSH username/password."
                    )
                ssh_password = decrypt_str(config.encrypted_ssh_password)
                ssh_username = config.ssh_username
                proxmox_url = config.proxmox_url
                verify_ssl = config.verify_ssl

                user_public_keys: list[str] = []
                if user_ssh_key_ids:
                    from src.models import UserSSHKey as UserKey
                    user_keys = db.exec(
                        select(UserKey).where(
                            and_(UserKey.tenant_id == tenant_id, UserKey.id.in_(user_ssh_key_ids))
                        )
                    ).all()
                    user_public_keys = [k.public_key for k in user_keys]
            # ← DB session closed; all values captured in locals

            img = IMAGE_BY_ID.get(image_id)
            public_key, private_key_pem = generate_ed25519_keypair()

            os.makedirs(work_dir, exist_ok=True)
            tf_mgr = TerraformManager(work_dir)
            rendered = tf_mgr.render_template("proxmox_vm.tf.j2", {
                "proxmox_url": proxmox_url,
                "api_token": api_token,
                "insecure": not verify_ssl,
                "ssh_username": ssh_username,
                "ssh_password": ssh_password,
                "node_name": node_name,
                "vm_name": vm_name,
                "vmid": vmid,
                "cpu_cores": cpu_cores,
                "memory_mb": memory_mb,
                "disk_gb": disk_gb,
                "image_filename": img["filename"],
                "bridge": bridge,
                "cloud_init_user": cloud_init_user,
                "ssh_public_keys": [public_key] + user_public_keys,
            })
            tf_mgr.write_config(rendered)

            logger.info("terraform_init_started", vmid=vmid, persist_db=True)
            tf_mgr.init()
            logger.info("terraform_apply_started", vmid=vmid, persist_db=True)
            outputs = tf_mgr.apply()

            state_json = tf_mgr.read_state()
            initial_ip = outputs.get("vm_ipv4") or None

            # Commit workspace + SSH key immediately after apply.
            # VM status stays "provisioning" — Phase 2 gates the flip to "running"
            # on a successful SSH port check. This guarantees the key is in the DB
            # before the VM is ever visible as ready in the UI.
            with Session(engine) as db:
                db.add(TerraformWorkspace(
                    vm_id=vm_id, tenant_id=tenant_id,
                    rendered_config=rendered, terraform_state=state_json,
                ))
                db.add(VMSSHKey(
                    vm_id=vm_id, tenant_id=tenant_id,
                    public_key=public_key,
                    private_key_encrypted=encrypt_str(private_key_pem),
                    key_type="ed25519",
                ))
                vm = db.exec(select(VM).where(VM.id == vm_id)).first()
                if vm:
                    vm.cloud_init_user = cloud_init_user
                    vm.cpu_cores = cpu_cores
                    vm.memory_mb = memory_mb
                    vm.disk_gb = disk_gb
                    if initial_ip:
                        vm.ip_address = initial_ip
                    vm.updated_at = datetime.now()
                    db.add(vm)
                db.commit()
                logger.info("vm_terraform_complete", vmid=vmid, name=vm_name, persist_db=True)
                provisioned_vmid = vmid

        except Exception as e:
            with Session(engine) as db:
                vm = db.exec(select(VM).where(VM.id == vm_id)).first()
                if vm:
                    vm.status = "error"
                    vm.updated_at = datetime.now()
                    db.add(vm)
                    db.commit()
            logger.error("vm_provision_failed", vm_id=vm_id, name=vm_name, error=str(e), exc_info=True, persist_db=True)
            raise
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

        # ── Phase 2: Readiness check via QEMU guest agent — no direct network needed ──
        #
        # The Celery worker runs in Docker and may have no route to the VM's IP, so a
        # direct TCP probe of port 22 won't work. Instead we use the Proxmox API:
        # the QEMU guest agent only reports a non-loopback IP *after* cloud-init
        # finishes and the network stack is up — which also means sshd has started.
        # Getting an IP from the agent is therefore a reliable readiness signal.
        #
        # Polling budget: 120 × 5s = 600s (10 min). Generous enough for slow images.
        if provisioned_vmid:
            logger.info("vm_waiting_for_ready", vmid=provisioned_vmid)
            ip = initial_ip
            agent_ready = False

            with Session(engine) as poll_db:
                try:
                    ip_adapter = _get_adapter(poll_db)
                    for attempt in range(120):  # up to 600s (120 × 5s)
                        time.sleep(5)
                        try:
                            ip = ip_adapter.get_vm_ip(node_name, provisioned_vmid)
                            if ip:
                                agent_ready = True
                                logger.info("vm_agent_ready", vmid=provisioned_vmid, ip=ip)
                                break
                        except Exception:
                            pass
                        if attempt % 12 == 11:  # log progress every ~60s
                            logger.info("vm_still_waiting", vmid=provisioned_vmid, elapsed_s=(attempt + 1) * 5)
                except Exception as e:
                    logger.warning("vm_agent_poll_error", vmid=provisioned_vmid, error=str(e))

            with Session(engine) as update_db:
                vm_record = update_db.exec(select(VM).where(VM.id == vm_id)).first()
                if vm_record:
                    if ip:
                        vm_record.ip_address = ip
                    vm_record.status = "running" if agent_ready else "provisioning"
                    vm_record.updated_at = datetime.now()
                    update_db.add(vm_record)
                    update_db.commit()
            logger.info(
                "vm_provisioned_terraform" if agent_ready else "vm_agent_timeout",
                vmid=provisioned_vmid, ip=ip, agent_ready=agent_ready, persist_db=True,
            )


@app.task(bind=True, soft_time_limit=600, time_limit=660)
def destroy_vm(self, vm_id: int, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.destroy_vm"):
        with Session(engine) as db:
            vm = db.exec(
                select(VM).where(and_(VM.tenant_id == tenant_id, VM.id == vm_id))
            ).first()
            if not vm:
                return

            # Teardown associated docker services first
            services = db.exec(
                select(DockerService).where(
                    and_(DockerService.tenant_id == tenant_id, DockerService.target_vmid == vm.vmid)
                )
            ).all()
            for svc in services:
                _teardown_docker_service(db, svc)

            # Load Terraform workspace
            workspace = db.exec(
                select(TerraformWorkspace).where(
                    and_(TerraformWorkspace.tenant_id == tenant_id, TerraformWorkspace.vm_id == vm_id)
                )
            ).first()

            work_dir = f"/tmp/tf_destroy_{vm_id}"
            try:
                if workspace:
                    try:
                        os.makedirs(work_dir, exist_ok=True)
                        tf_mgr = TerraformManager(work_dir)
                        tf_mgr.write_config(workspace.rendered_config)
                        if workspace.terraform_state:
                            tf_mgr.write_state(workspace.terraform_state)
                        tf_mgr.init()
                        tf_mgr.destroy()
                    except Exception as tf_err:
                        logger.warning(
                            "terraform_destroy_failed_fallback",
                            vm_id=vm_id, vmid=vm.vmid, error=str(tf_err),
                        )
                    finally:
                        # Always run adapter cleanup as a safety net.
                        # The Proxmox provider may only stop the VM (ACPI) without deleting it,
                        # or the state may be stale. Force-stop + delete via API to guarantee
                        # the VM is gone from Proxmox regardless of Terraform outcome.
                        if vm.vmid and vm.vmid > 0:
                            adapter = _get_adapter(db)
                            try:
                                adapter.stop_vm(vm.node_name, vm.vmid)
                            except Exception:
                                pass
                            # Retry delete: VM may still be stopping after the stop request
                            for attempt in range(6):  # up to ~15s
                                try:
                                    adapter.delete_vm(vm.node_name, vm.vmid)
                                    break
                                except Exception:
                                    if attempt < 5:
                                        time.sleep(3)
                    db.delete(workspace)
                else:
                    # No Terraform workspace — provisioning failed before state was saved,
                    # or this is a legacy VM. Best-effort Proxmox API cleanup.
                    if vm.vmid and vm.vmid > 0:
                        adapter = _get_adapter(db)
                        try:
                            adapter.stop_vm(vm.node_name, vm.vmid)
                        except Exception:
                            pass
                        for attempt in range(6):
                            try:
                                adapter.delete_vm(vm.node_name, vm.vmid)
                                break
                            except Exception:
                                if attempt < 5:
                                    time.sleep(3)

                # Delete SSH key record
                ssh_key = db.exec(
                    select(VMSSHKey).where(
                        and_(VMSSHKey.tenant_id == tenant_id, VMSSHKey.vm_id == vm_id)
                    )
                ).first()
                if ssh_key:
                    db.delete(ssh_key)

                db.delete(vm)
                db.commit()
                logger.info("vm_destroyed_terraform", vmid=vm.vmid, persist_db=True)

            except Exception as e:
                logger.error("vm_destroy_failed", vm_id=vm_id, error=str(e), exc_info=True, persist_db=True)
                raise
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Docker service deployment
# ---------------------------------------------------------------------------

@app.task(bind=True, max_retries=TASK_MAX_RETRIES, soft_time_limit=300, time_limit=360)
def deploy_docker_service(
    self,
    target_vmid: int,
    target_type: str,
    node_name: str,
    service_name: str,
    image_name: str,
    image_tag: str,
    internal_port: int,
    tenant_id: str,
    external_port: Optional[int] = None,
    proxy_type: str = "http",
    dns_hostname: Optional[str] = None,
):
    with tenant_context(tenant_id=tenant_id, service_name="worker.deploy_docker"):
        with Session(engine) as db:
            # Validate image against allowlist (plugins + local overrides)
            integration = IntegrationClient(db)
            allowed_images = integration.get_allowed_images()
            local_overrides = db.exec(select(AllowedImage)).all()
            all_allowed_names = {img["name"] for img in allowed_images} | {img.image_name for img in local_overrides}

            if image_name not in all_allowed_names:
                raise ValueError(f"Image '{image_name}' is not in the allowlist")

            adapter = _get_adapter(db)

            port_mapping = f"-p {external_port or internal_port}:{internal_port}"
            docker_cmd = ["docker", "run", "-d", "--name", service_name, port_mapping,
                          f"{image_name}:{image_tag}"]

            container_id = None
            dns_entry = None
            nginx_config_entry = None

            try:
                if target_type == "ct":
                    result = adapter.exec_ct(node_name, target_vmid, docker_cmd)
                else:
                    result = adapter.exec_vm(node_name, target_vmid, docker_cmd)

                container_id = result.get("out-data", "").strip()

                inspect_cmd = ["docker", "inspect", "--format", "{{.NetworkSettings.IPAddress}}", container_id]
                if target_type == "ct":
                    ip_result = adapter.exec_ct(node_name, target_vmid, inspect_cmd)
                else:
                    ip_result = adapter.exec_vm(node_name, target_vmid, inspect_cmd)

                container_ip = ip_result.get("out-data", "").strip() or "127.0.0.1"

                svc = DockerService(
                    tenant_id=tenant_id,
                    name=service_name,
                    image_name=image_name,
                    image_tag=image_tag,
                    target_vmid=target_vmid,
                    target_type=target_type,
                    node_name=node_name,
                    container_id=container_id,
                    internal_port=internal_port,
                    external_port=external_port,
                    status="running",
                )
                db.add(svc)
                db.flush()

                if dns_hostname:
                    try:
                        dns_entry = DNSEntry(
                            tenant_id=tenant_id,
                            hostname=dns_hostname,
                            ip_address=container_ip,
                            zone="default",
                        )
                        db.add(dns_entry)
                        db.flush()
                        adapter.add_dns_entry("default", dns_hostname, container_ip)
                        dns_entry.proxmox_synced = True
                        svc.dns_entry_id = dns_entry.id
                    except Exception as e:
                        logger.warning("dns_entry_failed", error=str(e))

                nginx_mgr = NginxConfigManager()
                config_filename = f"{tenant_id[:6]}-{service_name}.conf"

                if proxy_type == "http":
                    rendered = nginx_mgr.render_http(
                        service_name=service_name,
                        server_name=dns_hostname or f"{service_name}.local",
                        upstream_ip=container_ip,
                        upstream_port=internal_port,
                    )
                else:
                    rendered = nginx_mgr.render_stream(
                        service_name=service_name,
                        listen_port=external_port or internal_port,
                        upstream_ip=container_ip,
                        upstream_port=internal_port,
                    )

                nginx_config_entry = NginxConfig(
                    tenant_id=tenant_id,
                    service_name=service_name,
                    proxy_type=proxy_type,
                    server_name=dns_hostname or f"{service_name}.local",
                    upstream_ip=container_ip,
                    upstream_port=internal_port,
                    listen_port=external_port if proxy_type == "stream" else None,
                    config_filename=config_filename,
                    rendered_config=rendered,
                )
                db.add(nginx_config_entry)
                db.flush()

                nginx_mgr.write_config(nginx_config_entry)
                nginx_mgr.reload_nginx()

                svc.nginx_config_id = nginx_config_entry.id
                db.add(svc)
                db.commit()

                logger.info("docker_service_deployed", service=service_name, container_id=container_id, persist_db=True)

            except Exception as e:
                if container_id:
                    try:
                        rm_cmd = ["docker", "rm", "-f", container_id]
                        if target_type == "ct":
                            adapter.exec_ct(node_name, target_vmid, rm_cmd)
                        else:
                            adapter.exec_vm(node_name, target_vmid, rm_cmd)
                    except Exception:
                        pass

                if dns_entry and dns_entry.proxmox_synced:
                    try:
                        adapter.delete_dns_entry("default", dns_entry.hostname)
                    except Exception:
                        pass

                if nginx_config_entry:
                    try:
                        NginxConfigManager().delete_config(nginx_config_entry)
                    except Exception:
                        pass

                db.rollback()
                logger.error("docker_service_deploy_failed", service=service_name, error=str(e), exc_info=True, persist_db=True)
                raise


@app.task(bind=True, soft_time_limit=120, time_limit=180)
def remove_docker_service(self, service_id: int, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.remove_docker"):
        with Session(engine) as db:
            svc = db.exec(
                select(DockerService).where(
                    and_(DockerService.tenant_id == tenant_id, DockerService.id == service_id)
                )
            ).first()
            if not svc:
                return

            _teardown_docker_service(db, svc)
            db.commit()


def _teardown_docker_service(db: Session, svc: DockerService):
    """Remove a docker service: stop container, delete DNS, remove nginx config."""
    adapter = _get_adapter(db)
    nginx_mgr = NginxConfigManager()

    if svc.container_id:
        try:
            rm_cmd = ["docker", "rm", "-f", svc.container_id]
            if svc.target_type == "ct":
                adapter.exec_ct(svc.node_name, svc.target_vmid, rm_cmd)
            else:
                adapter.exec_vm(svc.node_name, svc.target_vmid, rm_cmd)
        except Exception as e:
            logger.warning("container_remove_failed", container_id=svc.container_id, error=str(e))

    if svc.dns_entry_id:
        dns = db.exec(select(DNSEntry).where(DNSEntry.id == svc.dns_entry_id)).first()
        if dns:
            try:
                adapter.delete_dns_entry(dns.zone, dns.hostname)
            except Exception:
                pass
            db.delete(dns)

    if svc.nginx_config_id:
        nginx_cfg = db.exec(select(NginxConfig).where(NginxConfig.id == svc.nginx_config_id)).first()
        if nginx_cfg:
            try:
                nginx_mgr.delete_config(nginx_cfg)
                nginx_mgr.reload_nginx()
            except Exception:
                pass
            db.delete(nginx_cfg)

    db.delete(svc)


# ---------------------------------------------------------------------------
# Firewall / DNS sync helpers
# ---------------------------------------------------------------------------

@app.task(bind=True, soft_time_limit=60, time_limit=90)
def sync_firewall_rule(self, rule_id: int, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.firewall"):
        with Session(engine) as db:
            rule = db.exec(
                select(FirewallRule).where(
                    and_(FirewallRule.tenant_id == tenant_id, FirewallRule.id == rule_id)
                )
            ).first()
            if not rule:
                return

            adapter = _get_adapter(db)
            rule_payload = {
                "action": rule.action,
                "type": rule.type,
                "proto": rule.proto,
                "dport": rule.dport,
                "sport": rule.sport,
                "source": rule.source,
                "dest": rule.dest,
                "comment": rule.comment,
                "enable": 1 if rule.enable else 0,
            }
            rule_payload = {k: v for k, v in rule_payload.items() if v is not None}
            adapter.add_firewall_rule(rule.scope, rule_payload, node=rule.node_name, vmid=rule.vmid)
            rule.proxmox_synced = True
            db.add(rule)
            db.commit()


@app.task(bind=True, soft_time_limit=60, time_limit=90)
def sync_dns_entry(self, entry_id: int, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.dns"):
        with Session(engine) as db:
            entry = db.exec(
                select(DNSEntry).where(
                    and_(DNSEntry.tenant_id == tenant_id, DNSEntry.id == entry_id)
                )
            ).first()
            if not entry:
                return

            adapter = _get_adapter(db)
            adapter.add_dns_entry(entry.zone, entry.hostname, entry.ip_address, entry.record_type)
            entry.proxmox_synced = True
            db.add(entry)
            db.commit()


@app.task(bind=True, soft_time_limit=60, time_limit=90)
def sync_all_dns(self, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.dns"):
        with Session(engine) as db:
            entries = db.exec(
                select(DNSEntry).where(
                    and_(DNSEntry.tenant_id == tenant_id, DNSEntry.proxmox_synced == False)
                )
            ).all()
            adapter = _get_adapter(db)
            for entry in entries:
                try:
                    adapter.add_dns_entry(entry.zone, entry.hostname, entry.ip_address, entry.record_type)
                    entry.proxmox_synced = True
                    db.add(entry)
                except Exception as e:
                    logger.warning("dns_sync_failed", hostname=entry.hostname, error=str(e))
            db.commit()


# ---------------------------------------------------------------------------
# Nginx reload
# ---------------------------------------------------------------------------

@app.task(bind=True, soft_time_limit=60, time_limit=90)
def reload_nginx(self):
    with Session(engine) as db:
        configs = db.exec(select(NginxConfig).where(NginxConfig.is_active == True)).all()
        mgr = NginxConfigManager()
        for cfg in configs:
            try:
                mgr.write_config(cfg)
            except Exception as e:
                logger.warning("nginx_config_write_failed", config=cfg.config_filename, error=str(e))
        try:
            mgr.reload_nginx()
        except Exception as e:
            logger.error("nginx_reload_failed", error=str(e))


# ---------------------------------------------------------------------------
# Plugin management
# ---------------------------------------------------------------------------

@app.task(bind=True, max_retries=1, soft_time_limit=600, time_limit=660)
def install_plugin(self, repo_url: str, auth_token: Optional[str], env_overrides: dict):
    logger.info("plugin_install_started", repo_url=repo_url)

    runner = DockerComposeRunner()
    plugin_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")

    with Session(engine) as db:
        existing = db.exec(select(Plugin).where(Plugin.name == plugin_name)).first()
        if existing:
            raise ValueError(f"Plugin '{plugin_name}' is already installed")

        plugin_record = Plugin(
            name=plugin_name,
            repo_url=repo_url,
            encrypted_auth_token=encrypt_str(auth_token) if auth_token else None,
            plugin_dir="",
            compose_file="",
            base_url="",
            status="installing",
        )
        db.add(plugin_record)
        db.commit()
        db.refresh(plugin_record)

        try:
            plugin_dir = runner.clone(repo_url, auth_token, plugin_name)
            manifest = PluginManifest.from_file(f"{plugin_dir}/infra-plugin.yaml")

            plugin_record.plugin_dir = plugin_dir
            plugin_record.compose_file = manifest.compose_file
            plugin_record.version = manifest.version
            plugin_record.capabilities = json.dumps(manifest.capability_names())

            runner.up(plugin_dir, manifest.compose_file)

            base_url = f"http://{plugin_name}-backend:8000"
            plugin_record.base_url = base_url

            integration = IntegrationClient(db)
            for _ in range(30):
                plugin_record.base_url = base_url
                db.add(plugin_record)
                db.flush()
                if integration.check_health(plugin_record):
                    break
                time.sleep(5)
            else:
                raise RuntimeError("Plugin health check timed out after 150s")

            plugin_record.status = "running"
            db.add(plugin_record)
            db.commit()

            logger.info("plugin_installed", name=plugin_name, persist_db=True)

        except Exception as e:
            plugin_record.status = "failed"
            db.add(plugin_record)
            db.commit()
            try:
                runner.down(plugin_dir, manifest.compose_file if 'manifest' in dir() else "docker-compose.yaml")
                runner.remove_dir(plugin_dir if 'plugin_dir' in dir() else "")
            except Exception:
                pass
            logger.error("plugin_install_failed", name=plugin_name, error=str(e), exc_info=True)
            raise


@app.task(bind=True, soft_time_limit=120, time_limit=180)
def uninstall_plugin(self, plugin_id: int):
    with Session(engine) as db:
        plugin = db.exec(select(Plugin).where(Plugin.id == plugin_id)).first()
        if not plugin:
            return

        runner = DockerComposeRunner()
        try:
            runner.down(plugin.plugin_dir, plugin.compose_file)
        except Exception as e:
            logger.warning("plugin_down_failed", name=plugin.name, error=str(e))
        try:
            runner.remove_dir(plugin.plugin_dir)
        except Exception as e:
            logger.warning("plugin_dir_remove_failed", name=plugin.name, error=str(e))

        db.delete(plugin)
        db.commit()
        logger.info("plugin_uninstalled", name=plugin.name, persist_db=True)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def update_plugin(self, plugin_id: int):
    with Session(engine) as db:
        plugin = db.exec(select(Plugin).where(Plugin.id == plugin_id)).first()
        if not plugin:
            return

        runner = DockerComposeRunner()
        runner.pull(plugin.plugin_dir)
        runner.up(plugin.plugin_dir, plugin.compose_file)

        integration = IntegrationClient(db)
        for _ in range(30):
            if integration.check_health(plugin):
                break
            time.sleep(5)

        plugin.status = "running"
        plugin.updated_at = datetime.now()
        db.add(plugin)
        db.commit()
        logger.info("plugin_updated", name=plugin.name, persist_db=True)


@app.task(bind=True, soft_time_limit=60, time_limit=90)
def check_plugin_health(self):
    with Session(engine) as db:
        plugins = db.exec(select(Plugin).where(Plugin.status.in_(["running", "unreachable"]))).all()
        integration = IntegrationClient(db)
        for plugin in plugins:
            healthy = integration.check_health(plugin)
            new_status = "running" if healthy else "unreachable"
            if plugin.status != new_status:
                plugin.status = new_status
                db.add(plugin)
        db.commit()


# ---------------------------------------------------------------------------
# Log cleanup
# ---------------------------------------------------------------------------

@app.task(bind=True, soft_time_limit=120, time_limit=180)
def cleanup_old_logs(self, tenant_id: str, log_retention_period_d: int, log_size: int):
    with tenant_context(tenant_id=tenant_id, service_name="worker.log_cleanup"):
        with Session(engine) as db:
            from datetime import timedelta
            from sqlalchemy import delete as sa_delete
            cutoff = datetime.now() - timedelta(days=log_retention_period_d)
            db.exec(
                sa_delete(Logs).where(
                    and_(Logs.tenant_id == tenant_id, Logs.timestamp < cutoff)
                )
            )
            db.commit()
