"""Protocol-independent resource retrieval through fsspec."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import fsspec
from fsspec.utils import get_protocol

from graphrag.model.resource import Resource


class ResourceLoader:
    """Load local paths/file URIs, HTTP URLs and installed fsspec protocols.

    Options are supplied per protocol, e.g. authenticated HTTP headers or an S3
    client configuration. Storage options are kept out of source metadata.
    This utility retrieves content without tracking resource changes.
    """

    def __init__(
        self,
        storage_options: Mapping[str, Mapping[str, Any]] | None = None,
    ):
        self.storage_options = {
            key: dict(value) for key, value in (storage_options or {}).items()
        }

    def _location(
        self,
        uri: str | Path,
    ):
        value = str(uri)
        parts = urlsplit(value)
        if parts.scheme == "file":
            if parts.netloc not in {"", "localhost"}:
                raise ValueError("Only local file URIs are supported")
            value = unquote(parts.path)
        protocol = get_protocol(value)
        if protocol == "file":
            value = str(Path(value).expanduser().absolute())
        fs, path = fsspec.core.url_to_fs(
            value, **self.storage_options.get(protocol, {})
        )
        return fs, path, value, protocol

    def read(
        self,
        uri: str | Path,
        *,
        base_uri: str | None = None,
    ) -> Resource:
        fs, path, location, protocol = self._location(uri)
        with fs.open(path, "rb") as stream:
            content = stream.read()
        source = path if protocol == "file" else location
        return Resource(
            content=content,
            source=source,
            base_uri=base_uri
            or (Path(source).as_uri() if protocol == "file" else source),
        )
