from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.enums import (
    BOMSourceStatusEnum,
    FacilityEnum,
    ProjectStatusEnum,
    RoleEnum,
    SafetyLevelEnum,
    SubsystemEnum,
)


class UserCreate(BaseModel):
    name: str
    email: str
    role: RoleEnum = RoleEnum.STUDENT


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    role: RoleEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: RoleEnum


class HealthResponse(BaseModel):
    status: str
    database: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Project DTOs
# ---------------------------------------------------------------------------


class ProjectCreate(BaseModel):
    title: str
    description: str
    student_id: int


class ProjectStepRead(BaseModel):
    id: int
    project_id: int
    step_order: int
    subsystem: SubsystemEnum
    title: str
    instructions: str
    facility: Optional[FacilityEnum] = None
    safety_level: SafetyLevelEnum
    requires_steward_signoff: bool
    safety_notes: Optional[str] = None
    is_completed: bool
    safety_approved_by: Optional[int] = None
    safety_approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProjectBOMItemRead(BaseModel):
    id: int
    project_id: int
    part_name: str
    quantity_needed: int
    source_status: BOMSourceStatusEnum
    inventory_item_id: Optional[int] = None
    external_purchase_note: Optional[str] = None

    model_config = {"from_attributes": True}


class ProjectRead(BaseModel):
    id: int
    student_id: int
    title: str
    description: str
    status: ProjectStatusEnum
    created_at: datetime
    steps: list[ProjectStepRead] = []
    bom_items: list[ProjectBOMItemRead] = []

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Chat DTOs
# ---------------------------------------------------------------------------


class ProjectChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ProjectChatResponse(BaseModel):
    reply: str


# ---------------------------------------------------------------------------
# Error envelope
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    error: str
    message: str
    retryable: bool = False


# ---------------------------------------------------------------------------
# Steward Safety Sign-off DTOs
# ---------------------------------------------------------------------------


class StewardSignoffRequest(BaseModel):
    steward_id: int
    notes: Optional[str] = None


class StewardFlagRequest(BaseModel):
    steward_id: int
    reason: str


class StepCompleteToggle(BaseModel):
    student_id: int
    is_completed: bool


class PendingSignoffRead(BaseModel):
    step_id: int
    project_id: int
    project_title: str
    student_id: int
    student_name: str
    step_order: int
    subsystem: SubsystemEnum
    facility: Optional[FacilityEnum] = None
    title: str
    instructions: str
    safety_notes: Optional[str] = None
    safety_level: SafetyLevelEnum


# ---------------------------------------------------------------------------
# Inventory DTOs
# ---------------------------------------------------------------------------


class InventoryItemCreate(BaseModel):
    sku: str
    name: str
    category: str
    facility: FacilityEnum
    location: str
    quantity: int = 0
    unit: str = "pcs"
    updated_by: Optional[int] = None


class InventoryItemUpdate(BaseModel):
    quantity: Optional[int] = None
    location: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    facility: Optional[FacilityEnum] = None
    unit: Optional[str] = None
    updated_by: Optional[int] = None


class InventoryItemRead(BaseModel):
    id: int
    sku: str
    name: str
    category: str
    facility: FacilityEnum
    location: str
    quantity: int
    unit: str
    updated_by: Optional[int] = None
    updated_at: datetime

    model_config = {"from_attributes": True}


class CSVImportSummary(BaseModel):
    imported_count: int
    skipped_count: int
    errors: list[str] = []


# ---------------------------------------------------------------------------
# Classmate CAD 3D Tool Integration DTOs
# ---------------------------------------------------------------------------


class CADStatusResponse(BaseModel):
    status: str
    bridge_version: str
    webhook_url: Optional[str] = None
    supported_formats: list[str]


class CADExportStubRequest(BaseModel):
    project_id: int
    part_name: str
    format: str = "stl"
    parameters: dict = {}


class CADExportStubResponse(BaseModel):
    job_id: str
    status: str
    part_name: str
    download_stub_url: str
    note: str

