"""Version 1 workflow contracts, separate from provider/model choices.

Only a linear sequence with bounded review→implement returns is representable.
These contracts do not relax legacy bindings or enable new CLI permissions.
"""
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, JsonValue, field_validator, model_validator

from ..providers.base import Capability


Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')]
Permission = Literal['read_only', 'workspace_write']
FallbackCondition = Literal['rate_limited', 'quota_exhausted', 'unavailable']

# Server ceilings for schema v1. Attempts/duration match execution preflight;
# the step ceiling bounds future compilation, independently of user input.
MAX_ATTEMPTS = 20
MAX_TOTAL_STEPS = 10000
MAX_DURATION_S = 86400


class Contract(BaseModel):
    model_config = {'extra': 'forbid'}


class Step(Contract):
    id: Identifier
    per_task: bool = Field(default=False, strict=True)

    @field_validator('per_task', mode='before')
    @classmethod
    def boolean_scope(cls, value):
        # Literal[False] alone also accepts 0; keep plan as strict as other steps.
        if type(value) is not bool:
            raise ValueError('per_task must be a boolean')
        return value


class AgentStep(Step):
    requires: list[Capability] = Field(default_factory=list)

    @field_validator('requires')
    @classmethod
    def unique_capabilities(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Capabilities must be unique')
        return value


class PlanStep(AgentStep):
    type: Literal['plan']
    role: Literal['planner'] = 'planner'
    per_task: Literal[False] = False


class ImplementStep(AgentStep):
    type: Literal['implement']
    role: Literal['implementer'] = 'implementer'
    max_attempts: int = Field(default=3, ge=1, le=MAX_ATTEMPTS, strict=True)


class TestStep(Step):
    type: Literal['test']
    # Arbitrary shell text is never part of the workflow definition.
    command_profile: Literal['server_default'] = 'server_default'


class ReviewStep(AgentStep):
    type: Literal['review']
    role: Literal['reviewer'] = 'reviewer'
    on_reject: Optional[Identifier] = None


class DocumentStep(AgentStep):
    type: Literal['document']
    role: Literal['documenter'] = 'documenter'


class HumanGateStep(Step):
    type: Literal['human_gate']


WorkflowStep = Annotated[Union[
    PlanStep, ImplementStep, TestStep, ReviewStep, DocumentStep, HumanGateStep,
], Field(discriminator='type')]


class WorkflowLimits(Contract):
    max_total_steps: int = Field(default=200, ge=1, le=MAX_TOTAL_STEPS, strict=True)
    max_duration_s: int = Field(default=14400, ge=1, le=MAX_DURATION_S, strict=True)
    budget_usd: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, strict=True)


class ApprovalPolicy(Contract):
    require_tests: bool = Field(default=True, strict=True)
    require_reviewer: bool = Field(default=True, strict=True)
    human_gate_after_plan: bool = Field(default=False, strict=True)


class WorkflowDefinition(Contract):
    schema_version: Literal[1]
    name: str = Field(min_length=1, max_length=120, pattern=r'\S')
    steps: list[WorkflowStep] = Field(min_length=1, max_length=100)
    limits: WorkflowLimits = Field(default_factory=WorkflowLimits)
    approval: ApprovalPolicy = Field(default_factory=ApprovalPolicy)

    @field_validator('schema_version', mode='before')
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError('schema_version must be an integer')
        return value

    @model_validator(mode='after')
    def valid_structure(self):
        from .validation import validate_structure
        validate_structure(self)
        return self


class ProviderBinding(Contract):
    provider_config_id: Identifier
    model: Optional[str] = Field(default=None, min_length=1, max_length=256)
    permission: Permission = 'read_only'
    parameters: dict[str, JsonValue] = Field(default_factory=dict)


class FallbackBinding(ProviderBinding):
    on: list[FallbackCondition] = Field(min_length=1, max_length=3)

    @field_validator('on')
    @classmethod
    def unique_conditions(cls, value):
        if len(value) != len(set(value)):
            raise ValueError('Fallback conditions must be unique')
        return value


class StepBinding(ProviderBinding):
    fallbacks: list[FallbackBinding] = Field(default_factory=list, max_length=10)
