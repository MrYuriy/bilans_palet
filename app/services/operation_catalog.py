"""The operations of the warehouse and how each one changes the stock.

The one place to add an operation, rename it, or change who may enter it.
"""

from dataclasses import dataclass

from app.models.movement import MovementType

# Columns of the daily balance an operation adds up in.
RECEIPTS = "receipts"
SHIPMENTS = "shipments"
CORRECTIONS = "corrections"
RECLASSIFICATIONS = "reclassifications"


@dataclass(frozen=True)
class Operation:
    type: MovementType
    label: str
    # Permission module (see PermissionService) needed to enter it.
    module: str
    # Daily balance column.
    category: str
    # +1 adds to the stock, -1 takes from it; 0: special (the lines carry the sign).
    sign: int = 0
    note_required: bool = False
    # Only carrier types counted in reports, e.g. new EURO from a producer.
    counted_types_only: bool = False
    # Booked by an import (a file, another app), never entered by hand; the
    # module is then the one needed to run the import.
    imported: bool = False


# Permission modules.
OPERATIONS_MODULE = "operations"
RECLASSIFICATION_MODULE = "reclassification"
INVENTORY_MODULE = "inventory"

OPERATIONS: dict[MovementType, Operation] = {
    op.type: op
    for op in (
        Operation(
            MovementType.PRODUCER_RECEIPT,
            "Przyjęcie od producentów EURO",
            OPERATIONS_MODULE,
            RECEIPTS,
            sign=1,
            counted_types_only=True,
        ),
        Operation(
            MovementType.PRODUCER_SHIPMENT,
            "Wysyłka do producentów EURO",
            OPERATIONS_MODULE,
            SHIPMENTS,
            sign=-1,
        ),
        Operation(
            MovementType.ECOM_TRANSFER,
            "Przesunięcie na ECOM",
            OPERATIONS_MODULE,
            SHIPMENTS,
            sign=-1,
        ),
        Operation(
            MovementType.OTHER_RECEIPT,
            "Inne — przyjęcie",
            OPERATIONS_MODULE,
            RECEIPTS,
            sign=1,
            note_required=True,
        ),
        Operation(
            MovementType.OTHER_SHIPMENT,
            "Inne — wydanie",
            OPERATIONS_MODULE,
            SHIPMENTS,
            sign=-1,
            note_required=True,
        ),
        # From the Transplaner file. UKR is kept apart from the stores.
        Operation(
            MovementType.STORE_SHIPMENT,
            "Wysyłka do sklepów",
            OPERATIONS_MODULE,
            SHIPMENTS,
            sign=-1,
            imported=True,
        ),
        Operation(
            MovementType.STORE_RETURN,
            "Zwroty ze sklepów",
            OPERATIONS_MODULE,
            RECEIPTS,
            sign=1,
            imported=True,
        ),
        Operation(
            MovementType.UKR_SHIPMENT,
            "Wysyłka UKR",
            OPERATIONS_MODULE,
            SHIPMENTS,
            sign=-1,
            imported=True,
        ),
        Operation(
            MovementType.UKR_RETURN,
            "Zwroty z UKR",
            OPERATIONS_MODULE,
            RECEIPTS,
            sign=1,
            imported=True,
        ),
        # Signed: each line says + or -.
        Operation(
            MovementType.CORRECTION,
            "Korekta stanu",
            OPERATIONS_MODULE,
            CORRECTIONS,
            note_required=True,
        ),
        # Off one carrier type, onto another.
        Operation(
            MovementType.RECLASSIFICATION,
            "Przeksięgowanie",
            RECLASSIFICATION_MODULE,
            RECLASSIFICATIONS,
            note_required=True,
        ),
        # Entered with the count sheet (InventoryService), not as a movement.
        Operation(
            MovementType.INVENTORY,
            "Inwentaryzacja",
            INVENTORY_MODULE,
            CORRECTIONS,
        ),
    )
}

# Every movement type needs its entry above.
assert set(OPERATIONS) == set(MovementType)
