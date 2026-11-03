from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel

from app.models.enums import (
    BOMSourceStatusEnum,
    FacilityEnum,
    ProjectStatusEnum,
    RoleEnum,
    SafetyLevelEnum,
    SubsystemEnum,
)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(unique=True, index=True, max_length=255)
    role: RoleEnum = Field(default=RoleEnum.STUDENT, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: Optional[int] = Field(default=None, primary_key=True)
    student_id: int = Field(foreign_key="users.id", index=True)
    title: str = Field(min_length=1, max_length=200)
    description: str
    status: ProjectStatusEnum = Field(default=ProjectStatusEnum.DRAFT, index=True)
    # Future hook for classmate's CAD tool integration
    cad_reference_url: Optional[str] = Field(default=None, max_length=500)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectStep(SQLModel, table=True):
    __tablename__ = "project_steps"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    step_order: int = Field(ge=1)
    subsystem: SubsystemEnum = Field(default=SubsystemEnum.ASSEMBLY)
    title: str = Field(min_length=1, max_length=200)
    instructions: str
    facility: Optional[FacilityEnum] = Field(default=None)
    safety_level: SafetyLevelEnum = Field(default=SafetyLevelEnum.NORMAL)
    requires_steward_signoff: bool = Field(default=False, index=True)
    safety_notes: Optional[str] = Field(default=None)
    is_completed: bool = Field(default=False)
    safety_approved_by: Optional[int] = Field(default=None, foreign_key="users.id")
    safety_approved_at: Optional[datetime] = Field(default=None)


class InventoryItem(SQLModel, table=True):
    __tablename__ = "inventory_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(unique=True, index=True, max_length=64)
    name: str = Field(index=True, max_length=200)
    category: str = Field(max_length=100)
    facility: FacilityEnum = Field(index=True)
    location: str = Field(max_length=120)
    quantity: int = Field(default=0, ge=0)
    unit: str = Field(default="pcs", max_length=32)
    updated_by: Optional[int] = Field(default=None, foreign_key="users.id")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectBOMItem(SQLModel, table=True):
    __tablename__ = "project_bom_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id", index=True)
    part_name: str = Field(min_length=1, max_length=200)
    quantity_needed: int = Field(default=1, ge=1)
    source_status: BOMSourceStatusEnum = Field(
        default=BOMSourceStatusEnum.EXTERNAL_PURCHASE_NEEDED
    )
    inventory_item_id: Optional[int] = Field(
        default=None, foreign_key="inventory_items.id"
    )
    external_purchase_note: Optional[str] = Field(default=None)
