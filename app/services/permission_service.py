from typing import ClassVar

from app.services.operation_catalog import (
    INVENTORY_MODULE,
    OPERATIONS_MODULE,
    RECLASSIFICATION_MODULE,
)


class PermissionService:
    """Maps roles to the UI/API modules they may use.

    Each operation names the module it needs (operation_catalog), so who may
    enter what is decided here, in one table.
    """

    ROLE_PERMISSIONS: ClassVar[dict[str, frozenset[str]]] = {
        "admin": frozenset({"*"}),
        "operator": frozenset(
            {OPERATIONS_MODULE, RECLASSIFICATION_MODULE, INVENTORY_MODULE}
        ),
        "viewer": frozenset(),
    }

    # All modules, used by the frontend to gate the UI.
    ALL_MODULES: ClassVar[tuple[str, ...]] = (
        "audit",
        INVENTORY_MODULE,
        "masterdata",
        OPERATIONS_MODULE,
        RECLASSIFICATION_MODULE,
        "settings",
        "users",
    )

    def has_access(self, role: str, module: str) -> bool:
        permissions = self.ROLE_PERMISSIONS.get(role, frozenset())
        return "*" in permissions or module in permissions

    def allowed_modules(self, role: str) -> list[str]:
        return [m for m in self.ALL_MODULES if self.has_access(role, m)]
