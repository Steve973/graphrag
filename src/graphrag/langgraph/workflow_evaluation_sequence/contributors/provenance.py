"""Evidence/source enrichment for graph elements used by an answer."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated

from pydantic import BeforeValidator, Field, JsonValue

from graphrag.langgraph.workflow_evaluation_sequence.contributors.base import (
    ContributorArtifact,
    ContributorResult,
    ContributorStatus,
)
from graphrag.model.base import ContractModel, NonEmptyStr
from graphrag.utils import scalar_to_list


NEO4J_PROVENANCE_QUERY = """
MATCH (entity)
WHERE elementId(entity) IN $entity_ids
   OR EXISTS {
       MATCH (entity)-[considered]-()
       WHERE elementId(considered) IN $relationship_ids
   }
MATCH (entity)-[has_evidence:HAS_EVIDENCE]->(evidence)
MATCH (evidence)-[has_source:HAS_SOURCE]->(source)
RETURN elementId(entity) AS entity_id,
       elementId(has_evidence) AS has_evidence_id,
       elementId(evidence) AS evidence_id,
       elementId(has_source) AS has_source_id,
       elementId(source) AS source_id,
       properties(evidence) AS evidence,
       properties(source) AS source
""".strip()


class ProvenanceRequest(ContractModel):
    """Graph elements materially considered while producing the response."""

    entity_ids: Annotated[list[NonEmptyStr], BeforeValidator(scalar_to_list)] = Field(
        default_factory=list
    )
    relationship_ids: Annotated[
        list[NonEmptyStr], BeforeValidator(scalar_to_list)
    ] = Field(default_factory=list)


class ProvenancePath(ContractModel):
    """One ``entity -[:HAS_EVIDENCE]-> evidence -[:HAS_SOURCE]-> source`` path."""

    entity_id: NonEmptyStr
    has_evidence_id: NonEmptyStr
    evidence_id: NonEmptyStr
    has_source_id: NonEmptyStr
    source_id: NonEmptyStr
    evidence: dict[str, JsonValue] = Field(default_factory=dict)
    source: dict[str, JsonValue] = Field(default_factory=dict)


ProvenanceLookup = Callable[
    [ProvenanceRequest], Awaitable[Sequence[ProvenancePath]]
]


class EvidenceProvenanceContributor:
    """Resolve cited graph IDs to evidence and source material."""

    name = "graph.evidence_provenance"

    def __init__(self, lookup: ProvenanceLookup) -> None:
        self._lookup = lookup

    async def contribute(self, request: ProvenanceRequest) -> ContributorResult:
        if not (request.entity_ids or request.relationship_ids):
            return ContributorResult(
                contributor=self.name,
                status=ContributorStatus.SKIPPED,
                warnings=["No materially considered entity or relationship IDs supplied"],
            )
        try:
            paths = await self._lookup(request)
        except Exception as error:
            return ContributorResult(
                contributor=self.name,
                status=ContributorStatus.FAILED,
                warnings=[f"{type(error).__name__}: {error}"],
            )
        if not paths:
            return ContributorResult(
                contributor=self.name,
                status=ContributorStatus.SKIPPED,
                warnings=["No HAS_EVIDENCE/HAS_SOURCE paths were found"],
            )
        return ContributorResult(
            contributor=self.name,
            status=ContributorStatus.COMPLETED,
            artifacts=[
                ContributorArtifact(
                    kind="provenance_path",
                    data=path.model_dump(mode="json"),
                )
                for path in paths
            ],
        )
