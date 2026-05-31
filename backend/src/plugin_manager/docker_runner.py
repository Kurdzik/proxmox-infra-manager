import os
import subprocess
from typing import Optional

import git


class DockerComposeRunner:
    """Manages plugin Docker Compose stacks via the mounted Docker socket."""

    PLUGINS_BASE_DIR = os.environ.get("PLUGINS_BASE_DIR", "/plugins")

    def clone(self, repo_url: str, auth_token: Optional[str], plugin_name: str) -> str:
        """Clone a plugin repo and return the local directory path."""
        plugin_dir = os.path.join(self.PLUGINS_BASE_DIR, plugin_name)
        if os.path.exists(plugin_dir):
            raise ValueError(f"Plugin directory already exists: {plugin_dir}")

        if auth_token:
            # Inject token into HTTPS URL
            if repo_url.startswith("https://"):
                repo_url = repo_url.replace("https://", f"https://x-token:{auth_token}@")

        git.Repo.clone_from(repo_url, plugin_dir)
        return plugin_dir

    def pull(self, plugin_dir: str) -> None:
        repo = git.Repo(plugin_dir)
        repo.remotes.origin.pull()

    def up(self, plugin_dir: str, compose_file: str) -> None:
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "up", "-d", "--build"],
            cwd=plugin_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    def down(self, plugin_dir: str, compose_file: str) -> None:
        subprocess.run(
            ["docker", "compose", "-f", compose_file, "down"],
            cwd=plugin_dir,
            check=True,
            capture_output=True,
            text=True,
        )

    def remove_dir(self, plugin_dir: str) -> None:
        import shutil
        if os.path.exists(plugin_dir):
            shutil.rmtree(plugin_dir)

    def reload_nginx(self, container_name: str = "infra-manager-nginx") -> None:
        subprocess.run(
            ["docker", "exec", container_name, "nginx", "-s", "reload"],
            check=True,
            capture_output=True,
            text=True,
        )
