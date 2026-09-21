"""
Performs workflow initialization.
"""

from graphrag.config.graph_rag_config import GraphRagSettings
from graphrag.graph_store.provider import GraphProvider
from graphrag.model.base import WorkflowStatus
from graphrag.model.rag_state import GraphRagState


async def initialize_workflow(
    state: GraphRagState,
    *,
    provider: GraphProvider,
    settings: GraphRagSettings,
) -> dict[str, object]:
    """Load stable graph context for the question's selected profile."""

    profile_id = state.question.profile_id or settings.data_profile.id
    context = await provider.build_graph_context(profile_id)
    if context.profile_id != profile_id:
        raise ValueError(
            f"provider returned profile {context.profile_id!r}; expected {profile_id!r}"
        )
    return {"graph_context": context, "status": WorkflowStatus.INITIALIZING}
