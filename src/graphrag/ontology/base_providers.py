"""Abstract contract for ontology querying."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from graphrag.model.ontology import (
    OntologyContextLimits,
    OntologyDirection,
    OntologyEntity,
    OntologyNeighborhood,
    OntologyResolution,
    OntologySearchResult,
    OntologySource,
    OntologySparqlResult,
)


class OntologyProvider(ABC):
    """Shared query contract; RDFLib or a native ontology platform can implement it.

    Initialize providers during application startup. Native implementations
    must adapt results to the same domain contracts and traversal budgets.
    The service assembles context and applies text output limits.
    """

    @abstractmethod
    def initialize(self) -> OntologySource: ...

    @abstractmethod
    def get_entity(
        self,
        identifier: str,
    ) -> OntologyEntity: ...

    @abstractmethod
    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exact: bool = False,
    ) -> OntologySearchResult: ...

    @abstractmethod
    def resolve(
        self,
        term: str,
        *,
        limit: int = 10,
    ) -> OntologyResolution: ...

    @abstractmethod
    def neighborhood(
        self,
        identifiers: Sequence[str],
        *,
        direction: OntologyDirection = "both",
        predicates: Sequence[str] | None = None,
        limits: OntologyContextLimits | None = None,
    ) -> OntologyNeighborhood:
        """Return original triples within node/edge/depth budgets.

        Return full entity metadata and literal text; the service applies text
        output limits consistently across backends.
        """
        ...

    @abstractmethod
    def query_sparql(
        self,
        query: str,
        *,
        limit: int = 50,
    ) -> OntologySparqlResult: ...
