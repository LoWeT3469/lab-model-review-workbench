"""Input contract for the synthetic laboratory panel."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


# These are ingestion guardrails for the simulator, not clinical reference intervals.
FEATURES = {
    "hemoglobin_g_dl": ("Hemoglobin", "g/dL", 0, 30),
    "wbc_10e9_l": ("White blood cells", "10⁹/L", 0, 150),
    "platelets_10e9_l": ("Platelets", "10⁹/L", 0, 1500),
    "mcv_fl": ("Mean corpuscular volume", "fL", 20, 200),
}

AUDIENCE_NOTICE = (
    "Independent educational prototype using synthetic data. "
    "The score represents a simulated review label and has no clinical use."
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, str_strip_whitespace=True)


class Panel(Contract):
    hemoglobin_g_dl: Annotated[float, Field(strict=True, gt=0, le=30)]
    wbc_10e9_l: Annotated[float, Field(strict=True, gt=0, le=150)] | None
    platelets_10e9_l: Annotated[float, Field(strict=True, gt=0, le=1500)] | None
    mcv_fl: Annotated[float, Field(strict=True, gt=20, le=200)] | None

    @model_validator(mode="after")
    def require_most_measurements(self):
        if sum(value is None for value in self.model_dump().values()) > 1:
            raise ValueError("At most one optional measurement may be null")
        return self


class PredictionRequest(Contract):
    request_id: UUID
    panel: Panel


class Review(Contract):
    review_id: UUID
    reviewer: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    disposition: Literal["accepted", "flagged"]
    note: Annotated[str, StringConstraints(max_length=1000)] = ""

    @model_validator(mode="after")
    def require_flag_reason(self):
        if self.disposition == "flagged" and not self.note:
            raise ValueError("A flagged review requires a note")
        return self


class Activation(Contract):
    version: str
    reason: Annotated[str, StringConstraints(min_length=1, max_length=200)]
