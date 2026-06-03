import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlmodel import Session, select

from src.models import NginxConfig

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))


class NginxConfigManager:
    NGINX_CONF_DIR = os.environ.get("NGINX_CONF_DIR", "/etc/nginx/conf.d")
    NGINX_STREAM_DIR = os.environ.get("NGINX_STREAM_DIR", "/etc/nginx/stream.d")
    NGINX_CONTAINER_NAME = os.environ.get("NGINX_CONTAINER_NAME", "infra-manager-nginx")

    def render_http(self, service_name: str, server_name: str, upstream_ip: str, upstream_port: int) -> str:
        upstream = _jinja_env.get_template("http_upstream.conf.j2").render(
            service_name=service_name,
            upstream_ip=upstream_ip,
            upstream_port=upstream_port,
        )
        server = _jinja_env.get_template("http_server.conf.j2").render(
            service_name=service_name,
            server_name=server_name,
        )
        return upstream + "\n" + server

    def render_stream(
        self, service_name: str, listen_port: int, upstream_ip: str, upstream_port: int
    ) -> str:
        upstream = _jinja_env.get_template("stream_upstream.conf.j2").render(
            service_name=service_name,
            upstream_ip=upstream_ip,
            upstream_port=upstream_port,
        )
        server = _jinja_env.get_template("stream_server.conf.j2").render(
            service_name=service_name,
            listen_port=listen_port,
        )
        return upstream + "\n" + server

    def write_config(self, config: NginxConfig) -> None:
        target_dir = self.NGINX_CONF_DIR if config.proxy_type == "http" else self.NGINX_STREAM_DIR
        path = os.path.join(target_dir, config.config_filename)
        with open(path, "w") as f:
            f.write(config.rendered_config)

    def delete_config(self, config: NginxConfig) -> None:
        target_dir = self.NGINX_CONF_DIR if config.proxy_type == "http" else self.NGINX_STREAM_DIR
        path = os.path.join(target_dir, config.config_filename)
        if os.path.exists(path):
            os.remove(path)

    def allocate_stream_port(self, db: Session, range_start: int, range_end: int) -> int:
        """Find the lowest unused TCP port in [range_start, range_end] across all stream configs."""
        used_ports = set(
            db.exec(
                select(NginxConfig.listen_port).where(
                    NginxConfig.proxy_type == "stream",
                    NginxConfig.listen_port >= range_start,
                    NginxConfig.listen_port <= range_end,
                )
            ).all()
        )
        for port in range(range_start, range_end + 1):
            if port not in used_ports:
                return port
        raise RuntimeError(f"No free ports available in range {range_start}–{range_end}")

    def reload_nginx(self) -> None:
        import docker
        client = docker.from_env()
        try:
            container = client.containers.get(self.NGINX_CONTAINER_NAME)
            container.kill(signal="HUP")
        except docker.errors.NotFound:
            raise RuntimeError(f"nginx container '{self.NGINX_CONTAINER_NAME}' not found")
        except docker.errors.APIError as e:
            raise RuntimeError(f"nginx reload failed: {e}")
        finally:
            client.close()
