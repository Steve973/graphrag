"""Exact tool name, argument, and optional sequence accuracy contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.tool_calls import (
    ToolCallEvaluationInputs,
    to_ragas_tool_inputs,
)


class ToolCallAccuracyContributor(RagasMetricContributor[ToolCallEvaluationInputs]):
    definition = MetricDefinition(
        "tool_call_accuracy",
        ("actual_tool_calls", "reference_tool_calls"),
        allow_empty_fields=("actual_tool_calls", "reference_tool_calls"),
    )

    def __init__(self, *, strict_order: bool = True) -> None:
        from ragas.metrics.collections import ToolCallAccuracy

        self.metric = ToolCallAccuracy(strict_order=strict_order)

    async def score(self, inputs: ToolCallEvaluationInputs) -> Any:
        messages, expected = to_ragas_tool_inputs(inputs)
        return await self.metric.ascore(
            user_input=messages,
            reference_tool_calls=expected,
        )
