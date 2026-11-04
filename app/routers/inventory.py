"""
Inventory router for HMC Makerspace, Machine Shop, Wood Shop, and EE Stockroom.

Mounted at /api/inventory.
"""

from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, col, or_, select

from app.database import get_session
from app.integrations.csv_import import parse_inventory_csv
from app.models.domain import InventoryItem, User
from app.models.enums import FacilityEnum, RoleEnum
from app.models.schemas import (
    CSVImportSummary,
    InventoryItemCreate,
    InventoryItemRead,
    InventoryItemUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("", response_model=List[InventoryItemRead])
def list_inventory(
    facility: Optional[FacilityEnum] = Query(default=None),
    category: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    """List inventory items with optional search and facility filters."""
    query = select(InventoryItem)

    if facility:
        query = query.where(InventoryItem.facility == facility)
    if category:
        query = query.where(InventoryItem.category == category)
    if search:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                col(InventoryItem.name).ilike(search_pattern),
                col(InventoryItem.sku).ilike(search_pattern),
                col(InventoryItem.category).ilike(search_pattern),
                col(InventoryItem.location).ilike(search_pattern),
            )
        )

    query = query.order_by(InventoryItem.name)
    items = session.exec(query).all()
    return [InventoryItemRead.model_validate(it) for it in items]


@router.post("", response_model=InventoryItemRead, status_code=201)
def create_inventory_item(
    payload: InventoryItemCreate,
    session: Session = Depends(get_session),
):
    """Add a new item to inventory."""
    existing = session.exec(
        select(InventoryItem).where(InventoryItem.sku == payload.sku)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Item with SKU '{payload.sku}' already exists",
        )

    item = InventoryItem(
        sku=payload.sku,
        name=payload.name,
        category=payload.category,
        facility=payload.facility,
        location=payload.location,
        quantity=payload.quantity,
        unit=payload.unit,
        updated_by=payload.updated_by,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    logger.info("Created inventory item %s (%s)", item.sku, item.name)
    return InventoryItemRead.model_validate(item)


@router.patch("/{item_id}", response_model=InventoryItemRead)
def update_inventory_item(
    item_id: int,
    payload: InventoryItemUpdate,
    session: Session = Depends(get_session),
):
    """Update stock quantity, location, or metadata for an item."""
    item = session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    if payload.quantity is not None:
        if payload.quantity < 0:
            raise HTTPException(
                status_code=400, detail="Quantity cannot be negative"
            )
        item.quantity = payload.quantity

    if payload.location is not None:
        item.location = payload.location
    if payload.name is not None:
        item.name = payload.name
    if payload.category is not None:
        item.category = payload.category
    if payload.facility is not None:
        item.facility = payload.facility
    if payload.unit is not None:
        item.unit = payload.unit
    if payload.updated_by is not None:
        item.updated_by = payload.updated_by

    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)

    return InventoryItemRead.model_validate(item)


@router.delete("/{item_id}", status_code=204)
def delete_inventory_item(
    item_id: int,
    session: Session = Depends(get_session),
):
    """Delete an item from inventory."""
    item = session.get(InventoryItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    session.delete(item)
    session.commit()
    return None


@router.post("/upload-csv", response_model=CSVImportSummary)
async def upload_inventory_csv(
    request: Request,
    steward_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Bulk import inventory records from CSV file, JSON payload, or raw text."""
    content = ""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        uploaded_file = form.get("file")
        if uploaded_file and hasattr(uploaded_file, "read"):
            raw_bytes = await uploaded_file.read()
            content = raw_bytes.decode("utf-8", errors="replace")
        elif "csv_text" in form:
            content = str(form["csv_text"])
    elif "application/json" in content_type:
        try:
            body_json = await request.json()
            if isinstance(body_json, str):
                content = body_json
            elif isinstance(body_json, dict):
                content = body_json.get("csv_text", "")
        except Exception:
            pass

    if not content:
        raw_body = await request.body()
        content = raw_body.decode("utf-8", errors="replace")

    if not content or not content.strip():
        raise HTTPException(
            status_code=400,
            detail="Either a CSV file or csv_text body must be provided",
        )

    parsed_items, parse_errors = parse_inventory_csv(content, steward_id=steward_id)

    imported_count = 0
    skipped_count = 0
    import_errors = list(parse_errors)

    for item in parsed_items:
        existing = session.exec(
            select(InventoryItem).where(InventoryItem.sku == item.sku)
        ).first()

        if existing:
            # Update existing quantity and location
            existing.quantity = item.quantity
            existing.location = item.location
            existing.category = item.category
            existing.facility = item.facility
            existing.updated_at = datetime.now(timezone.utc)
            if steward_id:
                existing.updated_by = steward_id
            session.add(existing)
            imported_count += 1
        else:
            session.add(item)
            imported_count += 1

    session.commit()
    return CSVImportSummary(
        imported_count=imported_count,
        skipped_count=skipped_count,
        errors=import_errors,
    )
