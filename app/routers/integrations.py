"""
Integrations router — CAD tool bridge and external fabrication endpoints.

Mounted at /api/integrations.
"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.integrations.cad_tool import CADToolService
from app.models.schemas import (
    CADExportStubRequest,
    CADExportStubResponse,
    CADStatusResponse,
)

router = APIRouter(prefix="/api/integrations", tags=["integrations"])

_cad_service = CADToolService()


def get_cad_service() -> CADToolService:
    return _cad_service


@router.get("/cad/status", response_model=CADStatusResponse)
def get_cad_bridge_status(
    service: CADToolService = Depends(get_cad_service),
):
    """Check connectivity and readiness of the classmate CAD 3D software bridge."""
    return service.get_status()


@router.post("/cad/export-stl-stub", response_model=CADExportStubResponse)
def export_stl_stub(
    payload: CADExportStubRequest,
    service: CADToolService = Depends(get_cad_service),
):
    """Trigger a mock STL/STEP export job for classmate's CAD software."""
    result = service.generate_export_stub(
        project_id=payload.project_id,
        part_name=payload.part_name,
        export_format=payload.format,
        parameters=payload.parameters,
    )
    return CADExportStubResponse.model_validate(result)

