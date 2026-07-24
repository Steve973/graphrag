from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import (
    BeforeValidator,
    Field,
    model_validator,
)

from graph_rag.model.base import (
    SupportStrength,
    ReasoningImpact,
    PlanStepStatus,
    NonEmptyStr,
    ContractModel
)
from graph_rag.utils import (
    new_id,
    scalar_to_list,
    utc_now
)


# =============================================================================
# PLAN AS THE CURRENT PROGRESS DOCUMENT
#
# A Plan keeps one stable ID across revisions. revision identifies the immutable
# snapshot currently being used. Each PlanStep owns accepted findings and its
# remaining unresolved items. SupportedFinding is a reasoned conclusion based on
# EvidenceRecord objects; it does not replace the evidence summaries themselves.
# =============================================================================


class SupportedFinding(ContractModel):
    """Represent a conclusion accepted as progress toward a plan step.

    Attributes:
        id: Stable finding identifier.
        statement: Conclusion or assertion accepted by the workflow.
        rationale: Explanation of how the cited evidence supports the finding.
        evidence_record_ids: Evidence records used to establish the finding.
        support_strength: Qualitative strength of the evidentiary support.
    """

    id: str = Field(
        default_factory=lambda: new_id("finding"),
        description=(
            "Stable finding identifier, normally generated automatically. Keep it stable "
            "while the same finding is carried across later plan revisions."
        ),
    )
    statement: NonEmptyStr = Field(
        description=(
            "A concise conclusion or assertion accepted as progress on the containing "
            "plan step. State the conclusion itself rather than copying evidence "
            "summaries or describing the retrieval process."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain the reasoning that connects the cited evidence summaries to the "
            "finding. Address meaningful inference or uncertainty; do not merely say that "
            "evidence supports the statement."
        ),
    )
    evidence_record_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        min_length=1,
        description=(
            "Exact EvidenceRecord IDs materially used to establish this finding. Every ID "
            "must resolve in the current working context, and unrelated evidence must not "
            "be cited."
        ),
    )
    support_strength: SupportStrength = Field(
        description=(
            "Qualitative strength of support: DIRECT when explicitly stated by evidence, "
            "STRONG for a low-uncertainty inference, MODERATE when meaningful inference "
            "or uncertainty remains, and TENTATIVE when provisional or weakly supported."
        ),
    )


class UnresolvedItem(ContractModel):
    """Represent information a plan step still lacks or cannot resolve.

    Attributes:
        id: Stable unresolved-item identifier.
        description: Missing fact, ambiguity, or unanswered sub-question.
        rationale: Explanation of why the item remains unresolved.
        impact: Effect of the unresolved item on answer completion.
        evidence_record_ids: Evidence that exposes, constrains, or partially
            addresses the unresolved item.
    """

    id: str = Field(
        default_factory=lambda: new_id("unresolved"),
        description=(
            "Stable identifier for this unresolved issue, normally generated "
            "automatically. Preserve it across plan revisions while it remains the same "
            "underlying issue."
        ),
    )
    description: NonEmptyStr = Field(
        description=(
            "Specific missing fact, ambiguity, unanswered sub-question, or conflict that "
            "still prevents or weakens completion of the containing plan step."
        ),
    )
    rationale: NonEmptyStr = Field(
        description=(
            "Explain why the item remains unresolved, what has already been learned, and "
            "why resolving it matters to the plan or answer."
        ),
    )
    impact: ReasoningImpact = Field(
        description=(
            "How strongly this unresolved item affects answer completion. Use BLOCKING "
            "only when a complete answer is unjustified without resolution; use MATERIAL "
            "when it substantially affects interpretation; use SUPPORTING or MINOR for "
            "nonessential improvements."
        ),
    )
    evidence_record_ids: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "EvidenceRecord IDs that reveal, constrain, or partially address this issue. "
            "Leave empty when the issue comes only from missing information; never cite "
            "unrelated evidence merely to populate the field."
        ),
    )


class PlanStep(ContractModel):
    """Track intended work and accepted progress for one investigation step.

    Attributes:
        id: Stable step identifier retained across plan revisions when the same
            conceptual step remains.
        description: Work the step is intended to accomplish.
        required: Whether a complete answer requires this step to be complete.
        status: Current progress state of the step.
        depends_on: IDs of plan steps that must precede this step.
        required_information: Information the step needs to resolve.
        completion_criteria: Conditions that establish the step as complete.
        supported_findings: Evidence-backed conclusions accepted for this step.
        unresolved_items: Remaining gaps associated with this step.
    """

    id: str = Field(
        default_factory=lambda: new_id("plan_step"),
        description=(
            "Stable identifier for this conceptual plan step. Preserve the same ID when "
            "editing the step in later revisions; assign a new ID only for a genuinely "
            "new step."
        ),
    )
    description: NonEmptyStr = Field(
        description=(
            "Clear statement of the investigative work this step must accomplish. It "
            "should be specific enough to guide action selection and progress evaluation."
        ),
    )
    required: bool = Field(
        default=True,
        description=(
            "Whether this step must be complete before the workflow may claim a COMPLETE "
            "answer. Set false only when the step is useful but genuinely optional."
        ),
    )
    status: PlanStepStatus = Field(
        default=PlanStepStatus.PENDING,
        description=(
            "Current status based on actual progress: PENDING before work, IN_PROGRESS "
            "while unresolved work remains, COMPLETE only when completion_criteria are "
            "satisfied, BLOCKED when a blocking issue prevents progress, or SKIPPED when "
            "an explicit evaluation determines the step is unnecessary."
        ),
    )
    depends_on: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "IDs of other steps that must be sufficiently resolved before this step can "
            "advance. Use exact current-plan step IDs, omit unrelated ordering, and never "
            "include this step’s own ID."
        ),
    )
    required_information: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Concrete information needed to perform or complete this step. Describe the "
            "needed facts or relationships, not the tool call expected to retrieve them."
        ),
    )
    completion_criteria: Annotated[
        list[NonEmptyStr],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Observable conditions that justify marking this step COMPLETE. Criteria "
            "should be testable against supported findings and resolved issues rather "
            "than vague statements such as \"enough information\"."
        ),
    )
    supported_findings: Annotated[
        list[SupportedFinding],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Evidence-backed conclusions already accepted for this step. Carry forward "
            "still-valid findings across revisions and remove or revise findings only "
            "when later evidence or reasoning invalidates them."
        ),
    )
    unresolved_items: Annotated[
        list[UnresolvedItem],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default_factory=list,
        description=(
            "Remaining issues associated with this step. Include what still needs to be "
            "resolved and its impact; remove an item only after it is actually resolved "
            "or rendered irrelevant by a documented plan revision."
        ),
    )


class Plan(ContractModel):
    """Act as the workflow's current progress-bearing investigation document.

    Attributes:
        id: Stable plan identity retained across revisions.
        revision: One-based immutable revision number for this plan snapshot.
        objective: Overall investigation objective derived from the question.
        steps: Ordered investigation steps and their accepted progress.
        expected_answer_shape: Optional guidance for the final response's form.
        created_at: UTC timestamp at which this revision was created.
    """

    id: str = Field(
        default_factory=lambda: new_id("plan"),
        description=(
            "Stable identity of the evolving investigation plan. A revised plan must "
            "retain this exact ID; revision history is represented by the revision field, "
            "not by generating a new plan ID."
        ),
    )
    revision: int = Field(
        default=1,
        ge=1,
        description=(
            "One-based revision number for this plan snapshot. The initial plan is 1; a "
            "successful revision of the current plan must use exactly current revision + "
            "1."
        ),
    )
    objective: NonEmptyStr = Field(
        default="unspecified",
        description=(
            "Overall investigation objective derived from the user’s question. Keep it "
            "focused on what must be determined to answer the request, not on a specific "
            "tool or implementation technique."
        ),
    )
    steps: Annotated[
        list[PlanStep],
        BeforeValidator(scalar_to_list),
    ] = Field(
        default=[],
        description=(
            "Ordered current plan steps, including their accepted findings and unresolved "
            "items. Preserve stable step IDs across revisions. This may be empty before "
            "planning; a plan used for an active iteration should contain actionable steps."
        ),
    )
    expected_answer_shape: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Optional guidance about the useful form or sections of the final answer. "
            "Describe output organization, not unsupported answer content."
        ),
    )
    created_at: datetime = Field(
        default_factory=utc_now,
        description=(
            "UTC timestamp generated when this plan revision is created. Omit it for a "
            "new plan or revision unless the application explicitly supplies it."
        ),
    )

    @model_validator(mode="after")
    def validate_plan(self) -> Plan:
        """Validate step identity, dependencies, and blocked-step semantics."""

        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("plan step ids must be unique")

        step_by_id = {step.id: step for step in self.steps}
        finding_ids: list[str] = []
        unresolved_ids: list[str] = []

        for step in self.steps:
            unknown_dependencies = set(step.depends_on) - set(step_by_id)
            if unknown_dependencies:
                raise ValueError(
                    f"plan step {step.id!r} depends on unknown steps: "
                    f"{sorted(unknown_dependencies)!r}"
                )
            if step.id in step.depends_on:
                raise ValueError(f"plan step {step.id!r} cannot depend on itself")

            incomplete_dependency = any(
                step_by_id[dependency_id].status != PlanStepStatus.COMPLETE
                for dependency_id in step.depends_on
            )
            blocking_item = any(
                item.impact == ReasoningImpact.BLOCKING
                for item in step.unresolved_items
            )

            if step.status == PlanStepStatus.BLOCKED:
                if not incomplete_dependency and not blocking_item:
                    raise ValueError(
                        f"blocked plan step {step.id!r} requires an incomplete "
                        "dependency or blocking unresolved item"
                    )

            if step.status == PlanStepStatus.COMPLETE:
                if incomplete_dependency:
                    raise ValueError(
                        f"complete plan step {step.id!r} has incomplete dependencies"
                    )
                if blocking_item:
                    raise ValueError(
                        f"complete plan step {step.id!r} has a blocking unresolved item"
                    )

            finding_ids.extend(item.id for item in step.supported_findings)
            unresolved_ids.extend(item.id for item in step.unresolved_items)

        if len(finding_ids) != len(set(finding_ids)):
            raise ValueError("supported finding ids must be unique within a plan")
        if len(unresolved_ids) != len(set(unresolved_ids)):
            raise ValueError("unresolved item ids must be unique within a plan")
        return self


class AddPlanStep(ContractModel):
    """Add a new step to the current plan.

    Attributes:
        type: Discriminator identifying an add-step change.
        step: Complete new plan step to insert.
        after_step_id: ID of the step after which the new step should be
            inserted. If null, the step is inserted at the beginning.
    """

    type: Literal["add_step"] = "add_step"
    step: PlanStep = Field(
        description="Complete new plan step to insert.",
    )
    after_step_id: NonEmptyStr | None = Field(
        default=None,
        description=(
            "ID of the existing step after which the new step should be "
            "inserted. Use null to insert it at the beginning."
        ),
    )


class ReplacePlanStep(ContractModel):
    """Replace an existing plan step with an updated step.

    The replacement may change any combination of the step's editable
    properties, including its status, dependencies, findings, unresolved
    items, required information, or completion criteria.

    Attributes:
        type: Discriminator identifying a replace-step change.
        step_id: ID of the existing step to replace.
        replacement: Complete replacement step.
    """

    type: Literal["replace_step"] = "replace_step"
    step_id: NonEmptyStr = Field(
        description="Exact ID of the existing plan step to replace.",
    )
    replacement: PlanStep = Field(
        description=(
            "Complete updated snapshot of the plan step. The replacement must "
            "preserve the replaced step ID."
        ),
    )


class RemovePlanStep(ContractModel):
    """Remove an existing step from the current plan.

    Attributes:
        type: Discriminator identifying a remove-step change.
        step_id: ID of the existing step to remove.
    """

    type: Literal["remove_step"] = "remove_step"
    step_id: NonEmptyStr = Field(
        description="Exact ID of the existing plan step to remove.",
    )


class MovePlanStep(ContractModel):
    """Move an existing step to another position in the current plan.

    Attributes:
        type: Discriminator identifying a move-step change.
        step_id: ID of the existing step to move.
        after_step_id: ID of the step after which the moved step should be
            placed. If null, the step is moved to the beginning.
    """

    type: Literal["move_step"] = "move_step"
    step_id: NonEmptyStr = Field(
        description="Exact ID of the existing plan step to move.",
    )
    after_step_id: NonEmptyStr | None = Field(
        default=None,
        description=(
            "ID of the existing step after which the moved step should be "
            "placed. Use null to move it to the beginning."
        ),
    )


class UpdatePlanProperties(ContractModel):
    """Update properties belonging to the plan itself.

    Attributes:
        type: Discriminator identifying a plan-property update.
        objective: Replacement investigation objective, when it must change.
        expected_answer_shape: Replacement guidance for the final answer's form,
            when it should change.
    """

    type: Literal["update_plan_properties"] = "update_plan_properties"
    objective: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Replacement investigation objective. Use null to leave the current "
            "objective unchanged."
        ),
    )
    expected_answer_shape: NonEmptyStr | None = Field(
        default=None,
        description=(
            "Replacement guidance for the final answer's form. Use null to leave "
            "the current expected answer shape unchanged."
        ),
    )

    @model_validator(mode="after")
    def validate_property_update(self) -> UpdatePlanProperties:
        """Ensure the property update has at least one actual property change."""

        if self.objective is None and self.expected_answer_shape is None:
            raise ValueError(
                "plan-property updates require at least one property value"
            )
        return self


PlanChange: TypeAlias = Annotated[
    AddPlanStep
    | ReplacePlanStep
    | RemovePlanStep
    | MovePlanStep
    | UpdatePlanProperties,
    Field(discriminator="type"),
]


class PlanUpdate(ContractModel):
    """Describe an ordered set of changes to apply to the current plan.

    The complete change set is applied as one update. After all changes are
    applied, the resulting plan snapshot is validated as a whole.

    Attributes:
        rationale: Explanation of why the plan changes are needed.
        changes: Ordered plan changes to apply.
    """

    rationale: NonEmptyStr = Field(
        description=(
            "Explain why the complete set of plan changes is needed, or why no "
            "changes are needed when the change list is empty."
        ),
    )
    changes: list[PlanChange] = Field(
        default_factory=list,
        description=(
            "Ordered changes to apply to the current plan as one validated "
            "update. Can be empty if no changes are needed."
        ),
    )

    @model_validator(mode="after")
    def validate_plan_update(self) -> PlanUpdate:
        """Validate consistency rules that do not require the current plan."""

        property_update_count = 0
        added_step_ids: list[str] = []
        replaced_step_ids: list[str] = []
        removed_step_ids: list[str] = []
        moved_step_ids: list[str] = []

        for change in self.changes:
            if isinstance(change, AddPlanStep):
                added_step_ids.append(change.step.id)
                if change.after_step_id == change.step.id:
                    raise ValueError(
                        f"added plan step {change.step.id!r} cannot be inserted "
                        "after itself"
                    )
            elif isinstance(change, ReplacePlanStep):
                replaced_step_ids.append(change.step_id)
                if change.replacement.id != change.step_id:
                    raise ValueError(
                        "replacement plan step must preserve the replaced step id"
                    )
            elif isinstance(change, RemovePlanStep):
                removed_step_ids.append(change.step_id)
            elif isinstance(change, MovePlanStep):
                moved_step_ids.append(change.step_id)
                if change.after_step_id == change.step_id:
                    raise ValueError(
                        f"moved plan step {change.step_id!r} cannot be placed "
                        "after itself"
                    )
            elif isinstance(change, UpdatePlanProperties):
                property_update_count += 1

        if property_update_count > 1:
            raise ValueError("plan update can contain at most one property update")

        if len(added_step_ids) != len(set(added_step_ids)):
            raise ValueError("plan update cannot add duplicate step ids")
        if len(replaced_step_ids) != len(set(replaced_step_ids)):
            raise ValueError("plan update cannot replace the same step more than once")
        if len(removed_step_ids) != len(set(removed_step_ids)):
            raise ValueError("plan update cannot remove the same step more than once")
        if len(moved_step_ids) != len(set(moved_step_ids)):
            raise ValueError("plan update cannot move the same step more than once")

        replaced_or_removed = set(replaced_step_ids) & set(removed_step_ids)
        if replaced_or_removed:
            raise ValueError(
                "plan update cannot both replace and remove steps: "
                f"{sorted(replaced_or_removed)!r}"
            )

        moved_removed = set(moved_step_ids) & set(removed_step_ids)
        if moved_removed:
            raise ValueError(
                "plan update cannot both move and remove steps: "
                f"{sorted(moved_removed)!r}"
            )

        return self
