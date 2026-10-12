"""Read-only Mobi entity access, independent of RDFLib exports."""

from __future__ import annotations

from collections.abc import Sequence
from threading import RLock
from typing import Any
from urllib.parse import quote, urlsplit

import httpx

from graphrag.config.ontology_config import OntologyReaderSettings
from graphrag.model.ontology import (
    OntologyContextLimits,
    OntologyDirection,
    OntologyEntity,
    OntologyNeighborhood,
    OntologyNotFoundError,
    OntologyQueryError,
    OntologyResolution,
    OntologySearchResult,
    OntologySource,
    OntologySparqlResult,
    OntologyUnsupportedError,
)
from graphrag.ontology.base_providers import OntologyProvider


class MobiOntologyProvider(OntologyProvider):
    """Read committed entity statements through Mobi's ontology REST API.

    ``endpoint`` is the REST base URL, typically https://host/mobirest.
    Supply an explicitly selected production commit and branch IRI. No default
    branch is assumed to represent production. Pass an authenticated httpx client
    when authentication is required; login/version discovery is not implemented.
    The existing reader settings supply annotation predicates, language and CURIE
    prefixes. No RDFLib parsing, storage, or query evaluation occurs here.
    """

    def __init__(
        self,
        endpoint: str,
        record_id: str,
        revision: str | None = None,
        *,
        branch_id: str | None = None,
        client: httpx.Client | None = None,
        settings: OntologyReaderSettings | None = None,
        include_imports: bool = False,
        server_version: str | None = None,
    ) -> None:
        location = urlsplit(endpoint)
        if (
            location.scheme not in {"http", "https"}
            or not location.netloc
            or location.username is not None
            or location.password is not None
            or location.query
            or location.fragment
        ):
            raise ValueError(
                "endpoint must be an HTTP(S) REST base URL without credentials, query or fragment"
            )
        if not record_id.strip():
            raise ValueError("record_id must be nonempty")
        if revision is not None and not revision.strip():
            raise ValueError("revision must be nonempty when supplied")
        if branch_id is not None and not branch_id.strip():
            raise ValueError("branch_id must be nonempty when supplied")
        self.endpoint = endpoint.rstrip("/")
        self.record_id = record_id
        self._ontology_url = f"{self.endpoint}/ontologies/{quote(record_id, safe='')}"
        self.revision = revision
        self.branch_id = branch_id
        self._settings = (settings or OntologyReaderSettings()).model_copy(deep=True)
        self._include_imports = include_imports
        self._server_version = server_version or "unknown"
        self._client = client or httpx.Client(timeout=30.0)
        self._owns_client = client is None
        self._source: OntologySource | None = None
        self._scope: dict[str, str] | None = None
        self._lock = RLock()

    def close(self) -> None:
        """Release the HTTP pool created here; injected clients remain caller-owned."""
        if self._owns_client:
            self._client.close()

    def _get(
        self,
        suffix: str,
        params: dict[str, str],
    ) -> Any:
        url = f"{self._ontology_url}/{suffix}"
        try:
            response = self._client.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                follow_redirects=False,
            )
            if not response.is_success:
                # Do not expose response bodies, cookies or authentication headers.
                raise OntologyQueryError(
                    f"Mobi read request returned HTTP {response.status_code}"
                )
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise OntologyQueryError(
                "Mobi read request failed or returned invalid JSON"
            ) from exc

    def initialize(self) -> OntologySource:
        with self._lock:
            if self._source is not None:
                return self._source
            if self.revision is None or self.branch_id is None:
                raise OntologyUnsupportedError(
                    "Supply the production branch_id and committed revision; automatic production-version selection is not implemented"
                )
            if self.revision.lower() in {"head", "latest", "master"}:
                raise OntologyUnsupportedError(
                    "Supply a fixed commit IRI, not a moving revision selector"
                )
            if self._include_imports and self._settings.unresolved_imports == "error":
                raise OntologyUnsupportedError(
                    "Strict import validation is pending a committed-only import API"
                )
            warnings = (
                (
                    "Imported ontology revisions and import failures are not verified by this provider",
                )
                if self._include_imports
                else (
                    "Ontology imports are excluded; production import-version selection is pending",
                )
            )
            self._scope = {
                "branchId": self.branch_id,
                "commitId": self.revision,
                "applyInProgressCommit": "false",
            }
            # Freeze the selected scope locally. The first entity read checks
            # server access without using edit-inclusive metadata endpoints.
            self._source = OntologySource(
                path=self._ontology_url,
                revision=self.revision,
                library="mobi",
                library_version=self._server_version,
                warnings=warnings,
            )
            if self._source is None:
                raise ValueError("Ontology source was not created")
            return self._source

    def _identifier(self, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Ontology identifier must be a nonempty string")
        value = value.strip()
        prefix, separator, local = value.partition(":")
        if separator and prefix in self._settings.prefixes:
            value = self._settings.prefixes[prefix] + local
        if not urlsplit(value).scheme or any(
            char.isspace() or char in '<>"{}|^`\\' for char in value
        ):
            raise ValueError("Supply an absolute IRI or a configured CURIE")
        return value

    def _entity(self, identifier: str, document: Any) -> OntologyEntity:
        if isinstance(document, dict) and "@context" in document:
            raise OntologyUnsupportedError(
                "Compact JSON-LD contexts are not supported by this provider"
            )
        if isinstance(document, dict) and "@graph" in document:
            document = document["@graph"]
        elif isinstance(document, dict):
            document = [document]
        if not isinstance(document, list) or any(
            not isinstance(node, dict) for node in document
        ):
            raise OntologyQueryError(
                "Mobi entity response must contain expanded JSON-LD nodes"
            )
        nodes = [node for node in document if node.get("@id") == identifier]
        if not nodes:
            if document:
                raise OntologyUnsupportedError(
                    "Mobi returned an unexpected entity identity or JSON-LD shape"
                )
            raise OntologyNotFoundError(f"No entity statements for {identifier!r}")
        if any("@context" in node for node in nodes):
            raise OntologyUnsupportedError(
                "Compact JSON-LD contexts are not supported by this provider"
            )

        def literals(predicates: Sequence[str]) -> list[str]:
            values: list[str] = []
            for predicate in predicates:
                annotations = []
                for node in nodes:
                    entries = node.get(self._identifier(predicate), [])
                    if not isinstance(entries, list):
                        raise OntologyQueryError(
                            "Expected expanded JSON-LD annotation arrays"
                        )
                    annotations.extend(
                        entry
                        for entry in entries
                        if isinstance(entry, dict) and "@value" in entry
                    )
                annotations.sort(
                    key=lambda entry: (
                        (
                            0
                            if entry.get("@language") == self._settings.language
                            else 1 if not entry.get("@language") else 2
                        ),
                        str(entry["@value"]),
                        str(entry.get("@language", "")),
                        str(entry.get("@type", "")),
                    )
                )
                values.extend(str(entry["@value"]) for entry in annotations)
            return list(dict.fromkeys(values))

        labels = literals(self._settings.label_predicates)
        definitions = literals(self._settings.definition_predicates)
        types: set[str] = set()
        for node in nodes:
            node_types = node.get("@type", [])
            if not isinstance(node_types, list) or any(
                not isinstance(value, str) for value in node_types
            ):
                raise OntologyQueryError("Expected expanded JSON-LD type arrays")
            types.update(node_types)
        return OntologyEntity(
            identifier=identifier,
            label=next(iter(labels), None),
            definition=next(iter(definitions), None),
            aliases=tuple(
                value
                for value in literals(self._settings.alias_predicates)
                if value not in labels
            ),
            types=tuple(sorted(types)),
        )

    def get_entity(
        self,
        identifier: str,
    ) -> OntologyEntity:
        identifier = self._identifier(identifier)
        with self._lock:
            self.initialize()
            assert self._scope is not None
            document = self._get(
                f"entities/{quote(identifier, safe='')}",
                {
                    **self._scope,
                    "format": "jsonld",
                    "includeImports": str(self._include_imports).lower(),
                },
            )
            return self._entity(identifier, document)

    def search(
        self,
        query: str,
        *,
        limit: int = 20,
        exact: bool = False,
    ) -> OntologySearchResult:
        raise OntologyUnsupportedError(
            "Mobi label/alias search is pending deployed API verification"
        )

    def resolve(
        self,
        term: str,
        *,
        limit: int = 10,
    ) -> OntologyResolution:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError("limit must be an integer between 1 and 200")
        if not isinstance(term, str) or not term.strip():
            raise ValueError("Ontology query must be a nonempty string")
        term = term.strip()
        if ":" not in term:
            raise OntologyUnsupportedError(
                "Mobi name/alias resolution is pending search implementation; supply an identifier"
            )
        try:
            entity = self.get_entity(term)
        except OntologyNotFoundError:
            return OntologyResolution(query=term, status="not_found", total_matches=0)
        return OntologyResolution(
            query=term, status="resolved", candidates=(entity,), total_matches=1
        )

    def neighborhood(
        self,
        identifiers: Sequence[str],
        *,
        direction: OntologyDirection = "both",
        predicates: Sequence[str] | None = None,
        limits: OntologyContextLimits | None = None,
    ) -> OntologyNeighborhood:
        raise OntologyUnsupportedError(
            "Mobi neighborhood traversal is pending query API and blank-node identity verification"
        )

    def query_sparql(self, query: str, *, limit: int = 50) -> OntologySparqlResult:
        # No arbitrary query is sent until read-only validation and scope are implemented.
        raise OntologyUnsupportedError(
            "Mobi SPARQL is pending deployed query API verification and read-only validation"
        )
