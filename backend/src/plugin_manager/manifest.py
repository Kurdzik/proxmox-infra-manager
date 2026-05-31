from dataclasses import dataclass, field
from typing import Optional
import yaml


@dataclass
class PluginCapabilityDef:
    name: str
    endpoint: str


@dataclass
class PluginIntegration:
    base_path: str
    capabilities: list[PluginCapabilityDef] = field(default_factory=list)


@dataclass
class PluginManifest:
    name: str
    version: str
    description: str
    compose_file: str
    env_vars: list[str]
    integration: PluginIntegration

    @classmethod
    def from_file(cls, path: str) -> "PluginManifest":
        with open(path, "r") as f:
            data = yaml.safe_load(f)

        required = ["name", "version", "compose_file", "integration"]
        for key in required:
            if key not in data:
                raise ValueError(f"Plugin manifest missing required field: {key}")

        integration_data = data["integration"]
        capabilities = [
            PluginCapabilityDef(name=cap["name"], endpoint=cap["endpoint"])
            for cap in integration_data.get("capabilities", [])
        ]

        return cls(
            name=data["name"],
            version=str(data.get("version", "unknown")),
            description=data.get("description", ""),
            compose_file=data["compose_file"],
            env_vars=data.get("env_vars", []),
            integration=PluginIntegration(
                base_path=integration_data.get("base_path", "/platform"),
                capabilities=capabilities,
            ),
        )

    def capability_names(self) -> list[str]:
        return [cap.name for cap in self.integration.capabilities]

    def endpoint_for(self, capability: str) -> Optional[str]:
        for cap in self.integration.capabilities:
            if cap.name == capability:
                return cap.endpoint
        return None
