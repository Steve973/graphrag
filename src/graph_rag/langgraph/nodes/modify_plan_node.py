"""Apply a model-proposed plan update deterministically."""

from graph_rag.model.plan import (
    AddPlanStep,
    MovePlanStep,
    Plan,
    PlanStep,
    RemovePlanStep,
    ReplacePlanStep,
    UpdatePlanProperties,
)
from graph_rag.model.rag_state import GraphRagState
from graph_rag.utils import utc_now


async def modify_plan(state: GraphRagState) -> dict[str, object]:
    """Apply all pending plan changes atomically and validate the new revision."""

    plan = state.plan
    update = state.pending_plan_update
    if plan is None or update is None:
        raise ValueError("plan modification requires a plan and pending update")
    if not update.changes:
        return {"pending_plan_update": None}

    steps = list(plan.steps)
    objective = plan.objective
    answer_shape = plan.expected_answer_shape
    for change in update.changes:
        if isinstance(change, AddPlanStep):
            _insert(steps, change.step, change.after_step_id)
        elif isinstance(change, ReplacePlanStep):
            index = _index(steps, change.step_id)
            steps[index] = change.replacement
        elif isinstance(change, RemovePlanStep):
            steps.pop(_index(steps, change.step_id))
        elif isinstance(change, MovePlanStep):
            step = steps.pop(_index(steps, change.step_id))
            _insert(steps, step, change.after_step_id)
        elif isinstance(change, UpdatePlanProperties):
            objective = change.objective or objective
            answer_shape = change.expected_answer_shape or answer_shape

    revised = Plan(
        id=plan.id,
        revision=plan.revision + 1,
        objective=objective,
        steps=steps,
        expected_answer_shape=answer_shape,
        created_at=utc_now(),
    )
    if not revised.steps:
        raise ValueError("an active plan cannot remove every step")
    return {"plan": revised, "pending_plan_update": None}


def _index(steps: list[PlanStep], step_id: str) -> int:
    """Return one existing step index or reject an unknown reference."""

    for index, step in enumerate(steps):
        if step.id == step_id:
            return index
    raise ValueError(f"plan update references unknown step {step_id!r}")


def _insert(
    steps: list[PlanStep],
    step: PlanStep,
    after_step_id: str | None,
) -> None:
    """Insert a plan step at the requested stable-ID position."""

    if any(item.id == step.id for item in steps):
        raise ValueError(f"plan step {step.id!r} already exists")
    index = 0 if after_step_id is None else _index(steps, after_step_id) + 1
    steps.insert(index, step)
