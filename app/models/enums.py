from enum import Enum


class RoleEnum(str, Enum):
    STUDENT = "student"
    STEWARD = "steward"


class ProjectStatusEnum(str, Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SubsystemEnum(str, Enum):
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    FIRMWARE = "firmware"
    AESTHETIC = "aesthetic"
    ASSEMBLY = "assembly"


class SafetyLevelEnum(str, Enum):
    NORMAL = "normal"
    STEWARD_SIGN_OFF_REQUIRED = "steward_sign_off_required"


class FacilityEnum(str, Enum):
    MACHINE_SHOP = "machine_shop"
    WOOD_SHOP = "wood_shop"
    EE_STOCKROOM = "ee_stockroom"
    MAKERSPACE = "makerspace"


class BOMSourceStatusEnum(str, Enum):
    IN_STOCK_ON_CAMPUS = "in_stock_on_campus"
    EXTERNAL_PURCHASE_NEEDED = "external_purchase_needed"
