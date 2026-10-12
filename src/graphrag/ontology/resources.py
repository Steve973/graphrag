"""An ontology source identified by URIs, independent of filesystem protocol."""

from __future__ import annotations

from collections.abc import Mapping

from graphrag.model.resource import Resource
from graphrag.resource_loader import ResourceLoader


class OntologyResources:
    """Retrieve an explicit root URI and explicit import URIs through fsspec.

    Ontology imports do not automatically cause arbitrary URI access: callers
    supply the import IRI-to-resource URI map. Authentication and protocol
    options live in the injected loader.
    """

    def __init__(
        self,
        uri: str,
        *,
        format: str | None = None,
        imports: Mapping[str, str] | None = None,
        loader: ResourceLoader | None = None,
    ):
        self.uri = uri
        self.format = format
        self.imports = dict(imports or {})
        self.loader = loader or ResourceLoader()

    def get_resource(self) -> Resource:
        return self.loader.read(self.uri)

    def get_import(
        self,
        ontology_iri: str,
    ) -> Resource | None:
        uri = self.imports.get(ontology_iri)
        return self.loader.read(uri) if uri is not None else None
