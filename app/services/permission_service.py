from typing import ClassVar


class PermissionService:
    """Maps roles to the UI/API modules they may use, and to the areas they reach.

    Modules are added phase by phase, as the features they guard appear.
    """

    ROLE_PERMISSIONS: ClassVar[dict[str, frozenset[str]]] = {
        "admin": frozenset({"*"}),
        "operator": frozenset({"movements"}),
        "viewer": frozenset(),
    }

    # All modules, used by the frontend to gate the UI.
    ALL_MODULES: ClassVar[tuple[str, ...]] = ("masterdata", "movements", "users")

    # Everyone else enters movements only in their assigned areas ...
    ENTERS_IN_ANY_AREA: ClassVar[frozenset[str]] = frozenset({"admin"})
    # ... and reads only those areas.
    READS_EVERY_AREA: ClassVar[frozenset[str]] = frozenset({"admin", "viewer"})

    def has_access(self, role: str, module: str) -> bool:
        permissions = self.ROLE_PERMISSIONS.get(role, frozenset())
        return "*" in permissions or module in permissions

    def allowed_modules(self, role: str) -> list[str]:
        return [m for m in self.ALL_MODULES if self.has_access(role, m)]

    def enters_in_any_area(self, role: str) -> bool:
        return role in self.ENTERS_IN_ANY_AREA

    def reads_every_area(self, role: str) -> bool:
        return role in self.READS_EVERY_AREA
