"""
CSV bulk import service for Makerspace, Machine Shop, Wood Shop, and EE Stockroom inventory.

Parses standard CSV records into InventoryItem model instances.
"""

import csv
import io
import logging
from typing import List, Optional, Tuple

from app.models.domain import InventoryItem
from app.models.enums import FacilityEnum

logger = logging.getLogger(__name__)

FACILITY_MAP = {
    "machine_shop": FacilityEnum.MACHINE_SHOP,
    "machineshop": FacilityEnum.MACHINE_SHOP,
    "machine shop": FacilityEnum.MACHINE_SHOP,
    "wood_shop": FacilityEnum.WOOD_SHOP,
    "woodshop": FacilityEnum.WOOD_SHOP,
    "wood shop": FacilityEnum.WOOD_SHOP,
    "ee_stockroom": FacilityEnum.EE_STOCKROOM,
    "eestockroom": FacilityEnum.EE_STOCKROOM,
    "ee stockroom": FacilityEnum.EE_STOCKROOM,
    "stockroom": FacilityEnum.EE_STOCKROOM,
    "makerspace": FacilityEnum.MAKERSPACE,
}


def parse_inventory_csv(
    csv_text: str, steward_id: Optional[int] = None
) -> Tuple[List[InventoryItem], List[str]]:
    """Parse CSV text and return a list of InventoryItem objects and any parse error messages.

    Expected CSV columns:
      sku, name, category, facility, location, quantity, unit
    """
    items: List[InventoryItem] = []
    errors: List[str] = []

    if not csv_text or not csv_text.strip():
        return items, ["CSV payload is empty."]

    reader = csv.DictReader(io.StringIO(csv_text.strip()))
    if not reader.fieldnames:
        return items, ["CSV header row missing or unreadable."]

    # Normalize fieldnames to lowercase stripped
    field_map = {fn.strip().lower(): fn for fn in reader.fieldnames if fn}
    required = ["sku", "name", "category", "facility", "location", "quantity"]
    missing = [col for col in required if col not in field_map]
    if missing:
        return items, [f"Missing required columns in CSV header: {', '.join(missing)}"]

    for row_idx, row in enumerate(reader, start=2):
        sku_val = row.get(field_map["sku"], "").strip()
        name_val = row.get(field_map["name"], "").strip()
        category_val = row.get(field_map["category"], "").strip()
        facility_str = row.get(field_map["facility"], "").strip().lower()
        location_val = row.get(field_map["location"], "").strip()
        quantity_str = row.get(field_map["quantity"], "").strip()
        unit_val = (
            row.get(field_map.get("unit", ""), "pcs").strip()
            if "unit" in field_map
            else "pcs"
        ) or "pcs"

        if not sku_val or not name_val:
            errors.append(f"Row {row_idx}: SKU and Name cannot be blank.")
            continue

        facility_enum = FACILITY_MAP.get(facility_str)
        if not facility_enum:
            errors.append(
                f"Row {row_idx} ({sku_val}): Invalid facility '{facility_str}'. "
                "Must be machine_shop, wood_shop, ee_stockroom, or makerspace."
            )
            continue

        try:
            qty = int(quantity_str)
            if qty < 0:
                raise ValueError()
        except ValueError:
            errors.append(
                f"Row {row_idx} ({sku_val}): Invalid quantity '{quantity_str}'. Must be a non-negative integer."
            )
            continue

        item = InventoryItem(
            sku=sku_val,
            name=name_val,
            category=category_val,
            facility=facility_enum,
            location=location_val,
            quantity=qty,
            unit=unit_val,
            updated_by=steward_id,
        )
        items.append(item)

    return items, errors

