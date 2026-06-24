from dataclasses import dataclass
from typing import Protocol


class AgentModule(Protocol):
    module_id: str


@dataclass(frozen=True)
class RegisteredModule:
    module_id: str
    description: str


class ModuleRegistry:
    def __init__(self) -> None:
        self._modules: dict[str, RegisteredModule] = {}

    def register(self, module: RegisteredModule) -> None:
        self._modules[module.module_id] = module

    def list_modules(self) -> list[RegisteredModule]:
        return list(self._modules.values())


DEFAULT_REGISTRY = ModuleRegistry()
DEFAULT_REGISTRY.register(
    RegisteredModule(
        module_id="fatigue_rest_stop",
        description="Recommends rest stops when fatigue risk rises on an active road-trip route.",
    )
)

