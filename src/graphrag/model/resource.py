"""Retrieved bytes and resource metadata."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Resource:
    """A resource's bytes and retrieval metadata, without content interpretation.

    source identifies the resource for provenance; base_uri supplies the base
    location for relative references. No change tracking is performed.
    """

    content: bytes
    source: str
    base_uri: str | None = None
