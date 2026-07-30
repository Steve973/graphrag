"""Persistable workflow audit contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from graph_rag.model.base import ContractModel, WorkflowStatus
from graph_rag.model.context import WorkingContext
from graph_rag.model.iteration import IterationRecord
from graph_rag.model.question import FinalAnswer, Question
from graph_rag.model.workflow import WorkflowError
from graph_rag.utils import utc_now


class CompletedWorkflowRecord(ContractModel):
    """Contain the complete forensic package for one terminal workflow.

    Attributes:
        workflow_id: Stable workflow and question identifier.
        question: Original question and unchanged execution limits.
        working_context: Final cumulative prompt-oriented context, absent only
            when initialization failed.
        iterations: Consecutive immutable iteration records, including raw tool
            results and their IDs.
        initialization_errors: Structured failures produced before iterations.
        status: Terminal workflow status.
        final_answer: Public answer returned to the caller.
        completed_at: Time at which the completed package was created.
    """

    workflow_id: str
    question: Question
    working_context: WorkingContext | None
    iterations: list[IterationRecord]
    initialization_errors: list[WorkflowError] = Field(default_factory=list)
    status: Literal[
        WorkflowStatus.COMPLETE,
        WorkflowStatus.PARTIAL,
        WorkflowStatus.NEEDS_CLARIFICATION,
        WorkflowStatus.FAILED,
    ]
    final_answer: FinalAnswer
    completed_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def validate_completed_workflow(self) -> CompletedWorkflowRecord:
        """Validate identifiers, terminal state, and iteration ordering."""

        if self.question.id != self.workflow_id:
            raise ValueError("question id must match workflow id")
        if self.final_answer.workflow_id != self.workflow_id:
            raise ValueError("final answer workflow id must match workflow id")
        if self.final_answer.status != self.status:
            raise ValueError("final answer status must match workflow status")
        if (
            self.working_context is not None
            and self.working_context.iteration_record_builder is not None
        ):
            raise ValueError("completed workflow cannot retain an active builder")
        if self.working_context is None and self.status != WorkflowStatus.FAILED:
            raise ValueError("only failed initialization may omit working context")

        numbers = [record.iteration_number for record in self.iterations]
        expected = list(range(1, len(self.iterations) + 1))
        if numbers != expected:
            raise ValueError("iteration records must be consecutive and ordered")
        return self
