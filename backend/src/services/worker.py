import json
import os
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
    Container,
    CTTemplate,
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
    VM,
    VMTemplate,
)
from src.nginx_manager import NginxConfigManager
from src.plugin_manager import DockerComposeRunner, IntegrationClient, PluginManifest
from src.proxmox import ProxmoxAdapterFactory, ProxmoxCredentials

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

            # list_nodes() often omits hardware details in cluster mode;
            # fall back to per-node status for memory, cpu_count, uptime.
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
                        vm.status = vm_data.get("status", "stopped")
                        vm.updated_at = datetime.now()
                        db.add(vm)

                cts = adapter.list_cts(node_name)
                for ct_data in cts:
                    vmid = ct_data.get("vmid")
                    ct = db.exec(select(Container).where(Container.vmid == vmid)).first()
                    if ct:
                        ct.status = ct_data.get("status", "stopped")
                        ct.updated_at = datetime.now()
                        db.add(ct)
            except Exception as e:
                logger.warning("node_sync_failed", node=node_name, error=str(e))

        db.commit()


# ---------------------------------------------------------------------------
# VM provisioning
# ---------------------------------------------------------------------------

@app.task(bind=True, max_retries=TASK_MAX_RETRIES, soft_time_limit=1800, time_limit=1860)
def provision_vm(self, template_id: int, node_name: str, vm_name: str, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.provision_vm"):
        with Session(engine) as db:
            with _tenant_provision_slot(tenant_id) as acquired:
                if not acquired:
                    raise self.retry(countdown=30)

                template = db.exec(
                    select(VMTemplate).where(
                        and_(VMTemplate.tenant_id == tenant_id, VMTemplate.id == template_id)
                    )
                ).first()
                if not template:
                    raise ValueError(f"Template {template_id} not found")

                adapter = _get_adapter(db)

                # ── Get-or-download ISO ──────────────────────────────────
                from src.images import IMAGE_BY_FILENAME, parse_storage_path
                parsed = parse_storage_path(template.os_image)
                if parsed:
                    storage, filename = parsed
                    try:
                        content = adapter.list_storage_content(node_name, storage, "iso")
                        existing = {item.get("volid", "").split("/")[-1] for item in content}
                        if filename not in existing:
                            img_meta = IMAGE_BY_FILENAME.get(filename)
                            if img_meta:
                                logger.info("iso_download_started", filename=filename, persist_db=True)
                                upid = adapter.download_iso(node_name, storage, img_meta["url"], filename)
                                adapter.wait_for_task(node_name, upid, poll_interval=10, timeout=1500)
                                logger.info("iso_download_complete", filename=filename, persist_db=True)
                            else:
                                logger.warning("iso_not_found_no_url", filename=filename)
                    except Exception as e:
                        logger.warning("iso_check_failed", error=str(e))
                # ────────────────────────────────────────────────────────

                existing_vmids = {v.get("vmid") for v in adapter.list_vms(node_name)}
                vmid = max(existing_vmids, default=99) + 1

                config = {
                    "name": vm_name,
                    "cores": template.cores,
                    "memory": template.memory_mb,
                    "scsihw": "virtio-scsi-single",
                    "scsi0": f"local-lvm:{template.disk_gb}",
                    "ide2": template.os_image,
                    "net0": f"{template.network_model},bridge=vmbr0",
                    "boot": "order=ide2;scsi0",
                }

                result = adapter.create_vm(node_name, vmid, config)

                vm = VM(
                    tenant_id=tenant_id,
                    vmid=vmid,
                    node_name=node_name,
                    name=vm_name,
                    status="provisioning",
                    template_id=template_id,
                )
                db.add(vm)
                db.commit()

                vnet = db.exec(select(TenantVNet).where(TenantVNet.tenant_id == tenant_id)).first()
                if vnet:
                    try:
                        adapter.assign_vnet_to_vm(node_name, vmid, vnet.vnet_id)
                    except Exception as e:
                        logger.warning("vnet_assignment_failed", vmid=vmid, error=str(e))

                adapter.start_vm(node_name, vmid)
                vm.status = "running"
                db.add(vm)
                db.commit()

                logger.info("vm_provisioned", vmid=vmid, name=vm_name, persist_db=True)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def destroy_vm(self, vm_id: int, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.destroy_vm"):
        with Session(engine) as db:
            vm = db.exec(
                select(VM).where(and_(VM.tenant_id == tenant_id, VM.id == vm_id))
            ).first()
            if not vm:
                return

            services = db.exec(
                select(DockerService).where(
                    and_(DockerService.tenant_id == tenant_id, DockerService.target_vmid == vm.vmid)
                )
            ).all()
            for svc in services:
                _teardown_docker_service(db, svc)

            adapter = _get_adapter(db)
            try:
                adapter.stop_vm(vm.node_name, vm.vmid)
            except Exception:
                pass
            adapter.delete_vm(vm.node_name, vm.vmid)

            db.delete(vm)
            db.commit()
            logger.info("vm_destroyed", vmid=vm.vmid, persist_db=True)


# ---------------------------------------------------------------------------
# Container provisioning
# ---------------------------------------------------------------------------

@app.task(bind=True, max_retries=TASK_MAX_RETRIES, soft_time_limit=600, time_limit=660)
def provision_ct(self, template_id: int, node_name: str, ct_name: str, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.provision_ct"):
        with Session(engine) as db:
            with _tenant_provision_slot(tenant_id) as acquired:
                if not acquired:
                    raise self.retry(countdown=30)

                template = db.exec(
                    select(CTTemplate).where(
                        and_(CTTemplate.tenant_id == tenant_id, CTTemplate.id == template_id)
                    )
                ).first()
                if not template:
                    raise ValueError(f"Template {template_id} not found")

                adapter = _get_adapter(db)

                existing_vmids = {c.get("vmid") for c in adapter.list_cts(node_name)}
                vmid = max(existing_vmids, default=99) + 1

                vnet = db.exec(select(TenantVNet).where(TenantVNet.tenant_id == tenant_id)).first()
                bridge = vnet.vnet_id if vnet else "vmbr0"

                config = {
                    "hostname": ct_name,
                    "cores": template.cores,
                    "memory": template.memory_mb,
                    "rootfs": f"local-lvm:{template.rootfs_gb}",
                    "ostemplate": template.os_template_url,
                    "net0": f"name=eth0,bridge={bridge}",
                    "unprivileged": 1,
                    "features": "nesting=1",  # required for Docker in LXC
                }

                adapter.create_ct(node_name, vmid, config)

                ct = Container(
                    tenant_id=tenant_id,
                    vmid=vmid,
                    node_name=node_name,
                    name=ct_name,
                    status="provisioning",
                    template_id=template_id,
                )
                db.add(ct)
                db.commit()

                adapter.start_ct(node_name, vmid)
                ct.status = "running"
                db.add(ct)
                db.commit()

                logger.info("ct_provisioned", vmid=vmid, name=ct_name, persist_db=True)


@app.task(bind=True, soft_time_limit=300, time_limit=360)
def destroy_ct(self, ct_id: int, tenant_id: str):
    with tenant_context(tenant_id=tenant_id, service_name="worker.destroy_ct"):
        with Session(engine) as db:
            ct = db.exec(
                select(Container).where(and_(Container.tenant_id == tenant_id, Container.id == ct_id))
            ).first()
            if not ct:
                return

            services = db.exec(
                select(DockerService).where(
                    and_(DockerService.tenant_id == tenant_id, DockerService.target_vmid == ct.vmid)
                )
            ).all()
            for svc in services:
                _teardown_docker_service(db, svc)

            adapter = _get_adapter(db)
            try:
                adapter.stop_ct(ct.node_name, ct.vmid)
            except Exception:
                pass
            adapter.delete_ct(ct.node_name, ct.vmid)

            db.delete(ct)
            db.commit()


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
                    config = db.exec(select(PlatformConfig)).first()
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
                # Rollback: stop container if started
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

            # Determine base URL from first container's network alias
            base_url = f"http://{plugin_name}-backend:8000"
            plugin_record.base_url = base_url

            # Poll health endpoint
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
