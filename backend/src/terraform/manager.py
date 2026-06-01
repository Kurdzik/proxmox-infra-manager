import json
import os
import subprocess
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES_DIR = Path(__file__).parent / "templates"


class TerraformError(Exception):
    """Raised when a terraform command exits with a non-zero return code.

    Plain single-string Exception so Celery can pickle/unpickle it without
    an UnpickleableExceptionWrapper. Build the message before raising.
    """


class TerraformManager:
    """Manages Terraform lifecycle for a single VM workspace.

    All file operations are scoped to `work_dir`. The directory must exist
    before calling write_config / write_state.
    """

    def __init__(self, work_dir: str) -> None:
        self.work_dir = work_dir

    # ------------------------------------------------------------------
    # Template rendering
    # ------------------------------------------------------------------

    def render_template(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a Jinja2 .tf.j2 template from the templates directory."""
        env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            undefined=StrictUndefined,
            keep_trailing_newline=True,
        )
        template = env.get_template(template_name)
        return template.render(**context)

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------

    def write_config(self, tf_content: str) -> None:
        """Write rendered HCL content to main.tf in the work directory."""
        os.makedirs(self.work_dir, exist_ok=True)
        with open(os.path.join(self.work_dir, "main.tf"), "w") as f:
            f.write(tf_content)

    def write_state(self, state_json: str) -> None:
        """Write terraform.tfstate to the work directory (used for destroy)."""
        with open(os.path.join(self.work_dir, "terraform.tfstate"), "w") as f:
            f.write(state_json)

    def read_state(self) -> str:
        """Read and return the terraform.tfstate content after apply."""
        state_path = os.path.join(self.work_dir, "terraform.tfstate")
        if not os.path.exists(state_path):
            return "{}"
        with open(state_path) as f:
            return f.read()

    # ------------------------------------------------------------------
    # Terraform commands
    # ------------------------------------------------------------------

    def _run(self, args: list[str], timeout: int = 1700) -> subprocess.CompletedProcess:
        result = subprocess.run(
            ["terraform"] + args,
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result

    @staticmethod
    def _fmt_error(cmd: str, returncode: int, stderr: str, stdout: str = "") -> str:
        detail = (stderr + "\n" + stdout).strip()
        return f"terraform {cmd} failed (exit {returncode}): {detail[:2000]}"

    def init(self) -> None:
        """Run terraform init. Downloads providers into .terraform/ inside work_dir."""
        result = self._run(["init", "-no-color"])
        if result.returncode != 0:
            raise TerraformError(self._fmt_error("init", result.returncode, result.stderr, result.stdout))

    def apply(self) -> dict[str, Any]:
        """Run terraform apply and return the outputs dict.

        Uses -json flag to emit newline-delimited JSON log lines.
        Parses lines with type=="outputs" to extract output values.
        On failure, diagnostic lines (type=="diagnostic") are extracted for the error message.
        """
        result = self._run(["apply", "-auto-approve", "-json"])

        outputs: dict[str, Any] = {}
        diagnostics: list[str] = []

        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("type") == "outputs":
                raw = entry.get("outputs", {})
                outputs = {k: v.get("value") for k, v in raw.items()}
            elif entry.get("type") == "diagnostic":
                diag = entry.get("diagnostic", {})
                summary = diag.get("summary", "")
                detail = diag.get("detail", "")
                if summary:
                    diagnostics.append(f"{summary}: {detail}" if detail else summary)

        if result.returncode != 0:
            diag_str = "\n".join(diagnostics) if diagnostics else ""
            raise TerraformError(self._fmt_error("apply", result.returncode, result.stderr, diag_str or result.stdout))

        return outputs

    def destroy(self) -> None:
        """Run terraform destroy."""
        result = self._run(["destroy", "-auto-approve", "-no-color"])
        if result.returncode != 0:
            raise TerraformError(self._fmt_error("destroy", result.returncode, result.stderr, result.stdout))
