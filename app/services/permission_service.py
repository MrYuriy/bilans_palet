from typing import ClassVar

from app.services.operation_catalog import (
    INVENTORY_MODULE,
    OPERATIONS_MODULE,
    RECLASSIFICATION_MODULE,
)


class PermissionService:
    """Maps roles to the UI/API modules they may use.

    Each operation names the module it needs (operation_catalog), so who may
    enter what is decided here, in one table. Everyone signed in reads the
    stock, the balances and the register.

    The manager, controller and operator rights are provisional, until the
    manager details them.
    """

    ROLE_PERMISSIONS: ClassVar[dict[str, frozenset[str]]] = {
        # Everything, the configuration included.
        "admin": frozenset({"*"}),
        # Everything but the configuration (settings, dictionaries, users).
        "manager": frozenset(
            {OPERATIONS_MODULE, RECLASSIFICATION_MODULE, INVENTORY_MODULE, "audit"}
        ),
        # Kontroler: re-classifications and stock counts.
        "controller": frozenset({RECLASSIFICATION_MODULE, INVENTORY_MODULE}),
        # The everyday operations.
        "operator": frozenset({OPERATIONS_MODULE}),
        # Obserwator: reads only.
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
