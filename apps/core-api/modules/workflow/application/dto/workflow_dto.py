from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from shared_kernel.pydantic_types import UUIDStr


class TransitionSpec(BaseModel):
    name: str
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class WorkflowDefinitionCreateRequest(BaseModel):
    entity_type: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    states: list[str] = Field(min_length=1)
    transitions: list[TransitionSpec] = Field(min_length=1)

    @field_validator("transitions")
    @classmethod
    def _validate_transitions_reference_known_states(
        cls, value: list[TransitionSpec], info
    ) -> list[TransitionSpec]:
        states = set(info.data.get("states") or [])
        unknown = {t.from_ for t in value} | {t.to for t in value}
        unknown -= states
        if unknown:
            raise ValueError(f"انتقالات تشير إلى حالات غير معرَّفة: {', '.join(sorted(unknown))}")
        return value


class WorkflowDefinitionResponse(BaseModel):
    id: UUIDStr
    entity_type: str
    name: str
    states: list[str]
    transitions: list[dict]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowInstanceStartRequest(BaseModel):
    definition_id: UUIDStr
    entity_type: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=128)


class WorkflowInstanceTransitionRequest(BaseModel):
    transition_name: str = Field(min_length=1)


class WorkflowInstanceResponse(BaseModel):
    id: UUIDStr
    definition_id: UUIDStr
    entity_type: str
    entity_id: str
    current_state: str
    history: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}
