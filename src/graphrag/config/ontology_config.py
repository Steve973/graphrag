"""Configuration for reading an OWL/RDF ontology mounted on disk."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from graphrag.model.base import NonEmptyStr


class OntologySettings(BaseModel):
    """Select local RDF files and the annotations used by this ontology.

    ``.owl``/``.rdf``/``.xml`` default to RDF/XML; ``.ttl``, ``.nt`` and ``.n3``
    select their corresponding RDF parsers. Set ``format`` explicitly for an
    ambiguous extension; parser names are passed through to RDFLib. OWL/XML, Functional Syntax, Manchester Syntax and OBO
    must be exported to RDF/XML or Turtle first.

    ``imports`` maps an exact owl:imports IRI to a local file. Only reachable,
    explicitly mapped imports are loaded. No imports are downloaded. Missing
    mappings produce source warnings or fail initialization, per configuration.
    Annotation predicates may be full IRIs or prefixes declared in the files
    or in ``prefixes``. Preferred language falls back to untagged annotations,
    then other languages, deterministically.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    path: Path
    format: NonEmptyStr | None = None
    language: NonEmptyStr | None = "en"
    prefixes: dict[NonEmptyStr, NonEmptyStr] = Field(default_factory=dict)
    imports: dict[NonEmptyStr, Path] = Field(default_factory=dict)
    unresolved_imports: Literal["warn", "error"] = "warn"
    label_predicates: tuple[NonEmptyStr, ...] = Field(default=(
        "http://www.w3.org/2000/01/rdf-schema#label",
        "http://www.w3.org/2004/02/skos/core#prefLabel",
    ), min_length=1)
    definition_predicates: tuple[NonEmptyStr, ...] = (
        "http://purl.obolibrary.org/obo/IAO_0000115",
        "http://www.w3.org/2004/02/skos/core#definition",
    )
    alias_predicates: tuple[NonEmptyStr, ...] = (
        "http://www.w3.org/2004/02/skos/core#altLabel",
        "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym",
    )
