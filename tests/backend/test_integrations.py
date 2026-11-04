"""
Unit tests for external tool integration hooks (CAD tool bridge).
"""


def test_cad_bridge_status(client):
    res = client.get("/api/integrations/cad/status")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready_for_webhook"
    assert "stl" in data["supported_formats"]
    assert "bridge_version" in data


def test_cad_export_stl_stub(client):
    payload = {
        "project_id": 1,
        "part_name": "Drone Motor Mount",
        "format": "stl",
    }
    res = client.post("/api/integrations/cad/export-stl-stub", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "queued"
    assert "drone_motor_mount.stl" in data["download_stub_url"]
    assert "Classmate CAD Bridge" in data["note"]

