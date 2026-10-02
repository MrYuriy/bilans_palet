from typing import ClassVar


class PermissionService:
    """Maps roles to the UI/API modules they may use.

    Modules are added phase by phase, as the features they guard appear.
    """

    ROLE_PERMISSIONS: ClassVar[dict[str, frozenset[str]]] = {
        "admin": frozenset({"*"}),
        "operator": frozenset(),
        "viewer": frozenset(),
    }

    # All modules, used by the frontend to gate the UI.
    ALL_MODULES: ClassVar[tuple[str, ...]] = ("users",)

    def has_access(self, role: str, module: str) -> bool:
        permissions = self.ROLE_PERMISSIONS.get(role, frozenset())
        return "*" in permissions or module in permissions

    def allowed_modules(self, role: str) -> list[str]:
        return [m for m in self.ALL_MODULES if self.has_access(role, m)]
