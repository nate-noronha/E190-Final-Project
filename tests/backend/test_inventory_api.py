"""
Unit and integration tests for Makerspace and Campus Stockroom Inventory (Slice 5).

Verifies CRUD operations, search filters, and bulk CSV spreadsheet imports.
"""

from sqlmodel import Session, select

from app.models.domain import InventoryItem, User
from app.models.enums import FacilityEnum, RoleEnum


def test_inventory_crud(client, session: Session):
    # 1. Create item
    payload = {
        "sku": "MS-ALUM-6061",
        "name": "6061 Aluminum Plate 1/4 inch",
        "category": "Raw Stock",
        "facility": "machine_shop",
        "location": "Bin MS-01",
        "quantity": 10,
        "unit": "sheets",
    }
    create_res = client.post("/api/inventory", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    item_id = created["id"]
    assert created["sku"] == "MS-ALUM-6061"
    assert created["quantity"] == 10

    # 2. Get item in list
    list_res = client.get("/api/inventory")
    assert list_res.status_code == 200
    assert any(item["sku"] == "MS-ALUM-6061" for item in list_res.json())

    # 3. Patch quantity
    patch_res = client.patch(f"/api/inventory/{item_id}", json={"quantity": 15})
    assert patch_res.status_code == 200
    assert patch_res.json()["quantity"] == 15

    # 4. Delete item
    del_res = client.delete(f"/api/inventory/{item_id}")
    assert del_res.status_code == 204

    # 5. Verify deleted
    get_after = client.get(f"/api/inventory?search=MS-ALUM-6061")
    assert len(get_after.json()) == 0


def test_inventory_search_and_facility_filter(client, session: Session):
    item1 = InventoryItem(
        sku="EE-RES-10K",
        name="10k Ohm Resistor 1/4W",
        category="Passives",
        facility=FacilityEnum.EE_STOCKROOM,
        location="Drawer R12",
        quantity=500,
    )
    item2 = InventoryItem(
        sku="MK-PLA-WHT",
        name="White PLA 1.75mm Spool",
        category="3D Printing",
        facility=FacilityEnum.MAKERSPACE,
        location="Shelf 3",
        quantity=8,
    )
    item3 = InventoryItem(
        sku="WS-OAK-01",
        name="Red Oak Board 1x4",
        category="Lumber",
        facility=FacilityEnum.WOOD_SHOP,
        location="Rack Wood",
        quantity=14,
    )
    session.add_all([item1, item2, item3])
    session.commit()

    # Search keyword
    res_search = client.get("/api/inventory?search=resistor")
    assert res_search.status_code == 200
    data = res_search.json()
    assert len(data) == 1
    assert data[0]["sku"] == "EE-RES-10K"

    # Filter facility
    res_fac = client.get("/api/inventory?facility=makerspace")
    assert res_fac.status_code == 200
    assert len(res_fac.json()) == 1
    assert res_fac.json()[0]["sku"] == "MK-PLA-WHT"


def test_bulk_csv_upload_import(client, session: Session):
    csv_payload = """sku,name,category,facility,location,quantity,unit
MS-TAP-M3,M3x0.5 Spiral Flute Tap,Cutting Tools,machine_shop,Drawer T1,5,pcs
EE-CAP-100U,100uF Electrolytic Capacitor,Passives,ee_stockroom,Drawer C4,50,pcs
MK-FIL-PETG,Prusament PETG Orange,3D Printing,makerspace,Bin P1,12,spools
"""
    res = client.post("/api/inventory/upload-csv", json=csv_payload)
    assert res.status_code == 200
    summary = res.json()
    assert summary["imported_count"] == 3
    assert len(summary["errors"]) == 0

    # Verify items were saved into database
    items = session.exec(select(InventoryItem)).all()
    skus = [i.sku for i in items]
    assert "MS-TAP-M3" in skus
    assert "EE-CAP-100U" in skus
    assert "MK-FIL-PETG" in skus


def test_bulk_csv_upload_updates_existing_and_reports_errors(client, session: Session):
    # Existing item
    existing = InventoryItem(
        sku="MS-BOLT-M4",
        name="M4 Bolt",
        category="Fasteners",
        facility=FacilityEnum.MACHINE_SHOP,
        location="Bin Old",
        quantity=20,
    )
    session.add(existing)
    session.commit()

    csv_payload = """sku,name,category,facility,location,quantity,unit
MS-BOLT-M4,M4 Bolt Updated,Fasteners,machine_shop,Bin New-02,35,pcs
INVALID-FAC,Mystery Item,Misc,moon_base,Unknown,10,pcs
"""
    res = client.post("/api/inventory/upload-csv", json=csv_payload)
    assert res.status_code == 200
    summary = res.json()
    assert summary["imported_count"] == 1
    assert len(summary["errors"]) == 1
    assert "Invalid facility 'moon_base'" in summary["errors"][0]

    # Verify existing item was updated
    session.refresh(existing)
    assert existing.quantity == 35
    assert existing.location == "Bin New-02"

