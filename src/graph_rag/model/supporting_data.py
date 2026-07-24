from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import (
    BeforeValidator,
    Field,
    model_validator,
)

from graph_rag.model.base import (
    ContractModel,
    ReasoningImpact,
    NonEmptyStr
)
from graph_rag.utils import (
    new_id,
    scalar_to_list,
    utc_now
)


# =============================================================================
# SUPPORTING DATA
#
# EvidenceRecord is an LLM-authored, prompt-friendly summary of one or more raw
# results. Subsequent reasoning carries evidence summaries rather than repeatedly
# copying raw result payloads into the model context.
# =============================================================================


class EvidenceRecord(ContractModel):
    """Carry a prompt-friendly interpretation of retained tool results.

    The LLM creates an evidence record after examining raw result data. The
    summary is the compact information carried forward for planning, evaluation,
    and answer generation. Raw data remains available through the referenced
    result IDs for verification or programmatic inspection.

    Attributes:
        id: Stable identifier referenced by findings and reasoning artifacts.
        summary: Concise textual interpretation of the relevant result data.
        source_result_ids: Raw tool-result IDs supporting the summary.
        created_at: UTC timestamp at which the evidence record was created.
    """

    id: str = Field(
        default_factory=lambda: new_id("evidence"),
        description=(
            "Stable identifier for this compact evidence interpretation. It is normally "
            "generated automatically; omit it when creating new evidence. Findings and "
            "other reasoning records cite this ID."
        ),
    )
    summary: NonEmptyStr = Field(
        description=(
            "Concise, prompt-friendly interpretation of the relevant facts, values, "
            "relationships, or absence of data in the cited raw tool results. Include the "
            "information later reasoning needs; do not copy the full raw payload, merely "
            "report tool success, or add claims the results do not support."
        ),
    )
    source_result_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        min_length=1,
        description=(
            "IDs of the retained ToolCallResult objects actually examined to produce this "
            "summary. Cite result IDs only, include every materially used result, exclude "
            "unrelated results, and never substitute request or evidence IDs."
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC timestamp generated when this interpretation is created. Omit it for new "
            "evidence unless the application explicitly supplies the timestamp."
        ),
    )

    @model_validator(mode="after")
    def validate_source_results(self) -> EvidenceRecord:
        """Reject duplicate source-result identifiers."""

        if len(self.source_result_ids) != len(set(self.source_result_ids)):
            raise ValueError("evidence source result ids must be unique")
        return self


class Assumption(ContractModel):
    """Record a proposition currently treated as true for reasoning purposes.

    Attributes:
        id: Stable assumption identifier.
        statement: Proposition being assumed.
        rationale: Explanation of why the workflow currently relies on it.
        impact: Effect of an incorrect or unresolved assumption on the answer.
        evidence_record_ids: Evidence that supports or prompted the assumption.
        affected_step_ids: Plan steps whose reasoning depends on the assumption.
    """

    id: str = Field(
        default_factory=lambda: new_id("assumption"),
        description=(
            "Stable identifier for this assumption, normally generated automatically. "
            "Preserve it while the same assumption remains active."
        ),
    )
    statement: NonEmptyStr = Field(
        description=(
            "Explicit proposition currently treated as true for reasoning even though it "
            "has not been fully established by evidence. Phrase it so it could later be "
            "confirmed, revised, or rejected."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain why this assumption is currently necessary or reasonable and how it "
            "affects the investigation. Do not present the assumption as an established "
            "fact."
        ),
    )
    impact: ReasoningImpact = Field(
        description=(
            "How strongly the assumption affects answer completion. Use BLOCKING when it "
            "must be verified for a complete answer, MATERIAL when it meaningfully "
            "affects confidence or interpretation, and SUPPORTING or MINOR for lesser "
            "effects."
        ),
    )
    evidence_record_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "EvidenceRecord IDs that motivate or partially support the assumption. This "
            "may be empty when the assumption arises from missing context; never cite "
            "evidence as though it fully proves an assumption."
        ),
    )
    affected_step_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Exact current-plan step IDs whose reasoning or completion depends on this "
            "assumption. Include all materially affected steps and no invented IDs."
        ),
    )


class Contradiction(ContractModel):
    """Record a conflict discovered in evidence or accepted plan progress.

    Attributes:
        id: Stable contradiction identifier.
        description: Textual explanation of the conflicting information.
        rationale: Explanation of why the cited information is contradictory.
        impact: Effect of the contradiction on answer completion.
        evidence_record_ids: Evidence records demonstrating the conflict.
        affected_step_ids: Plan steps whose progress or findings are affected.
    """

    id: str = Field(
        default_factory=lambda: new_id("contradiction"),
        description=(
            "Stable identifier for this contradiction, normally generated automatically. "
            "Preserve it while tracking the same unresolved conflict."
        ),
    )
    description: NonEmptyStr = Field(
        description=(
            "Specific conflict between evidence summaries, findings, assumptions, or plan "
            "expectations. State both sides clearly enough that the conflict can be "
            "investigated."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain why the cited information is genuinely inconsistent or materially in "
            "tension and how that conflict affects the investigation."
        ),
    )
    impact: ReasoningImpact = Field(
        description=(
            "How strongly this contradiction disrupts answer completion. Use BLOCKING "
            "when a complete answer is unjustified until resolved, MATERIAL for "
            "substantial uncertainty, and SUPPORTING or MINOR for lower-impact conflicts."
        ),
    )
    evidence_record_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        min_length=1,
        description=(
            "Exact EvidenceRecord IDs that demonstrate the conflicting information. Cite "
            "all material sides of the contradiction; do not use raw result or request "
            "IDs."
        ),
    )
    affected_step_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Exact current-plan step IDs whose findings, status, or completion are "
            "affected by this contradiction."
        ),
    )
