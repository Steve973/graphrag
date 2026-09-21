"""Set-based tool-call precision/recall/F1 contributor."""

from typing import Any

from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.base import (
    MetricDefinition,
    RagasMetricContributor,
)
from graphrag.langgraph.workflow_evaluation_sequence.contributors.ragas.tool_calls import (
    ToolCallEvaluationInputs,
    to_ragas_tool_inputs,
)


class ToolCallF1Contributor(RagasMetricContributor[ToolCallEvaluationInputs]):
    definition = MetricDefinition(
        "tool_call_f1",
        ("actual_tool_calls", "reference_tool_calls"),
        allow_empty_fields=("actual_tool_calls", "reference_tool_calls"),
    )

    def __init__(self) -> None:
        from ragas.metrics.collections import ToolCallF1

        self.metric = ToolCallF1()

    async def score(self, inputs: ToolCallEvaluationInputs) -> Any:
        messages, expected = to_ragas_tool_inputs(inputs)
        return await self.metric.ascore(
            user_input=messages,
            reference_tool_calls=expected,
        )
