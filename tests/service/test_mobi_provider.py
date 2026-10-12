"""Read-only HTTP contracts for the initial native Mobi implementation."""

import httpx
import pytest

from graphrag.config.ontology_config import OntologyReaderSettings
from graphrag.model.ontology import (
    OntologyQueryError,
    OntologyUnsupportedError,
)
from graphrag.ontology.mobi_provider import MobiOntologyProvider

IRI = 'https://example.org/Person'
LABEL = 'http://www.w3.org/2000/01/rdf-schema#label'
DEFINITION = 'http://www.w3.org/2004/02/skos/core#definition'
ALIAS = 'http://www.w3.org/2004/02/skos/core#altLabel'


def provider_with(handler, **kwargs):
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return MobiOntologyProvider(
        'https://mobi.example/mobirest', 'https://mobi.example/records#ontology',
        'https://mobi.example/commits#production',
        branch_id='https://mobi.example/branches#production', client=client,
        settings=OntologyReaderSettings(prefixes={'ex': 'https://example.org/'}),
        **kwargs,
    )


def test_entity_reads_are_committed_read_only_and_do_not_use_rdflib(monkeypatch):
    from rdflib import Graph

    def forbidden(*args, **kwargs):
        pytest.fail('Native Mobi access must not load or query RDFLib')

    monkeypatch.setattr(Graph, 'parse', forbidden)
    monkeypatch.setattr(Graph, 'query', forbidden)
    requests = []

    def handle(request):
        requests.append(request)
        assert request.method == 'GET'
        assert request.url.params['applyInProgressCommit'] == 'false'
        assert request.url.params['branchId'].endswith('#production')
        assert request.url.params['commitId'].endswith('#production')
        assert request.url.params['includeImports'] == 'false'
        assert 'records%23ontology' in request.url.raw_path.decode()
        assert 'https%3A%2F%2Fexample.org%2FPerson' in request.url.raw_path.decode()
        return httpx.Response(200, json=[{
            '@id': IRI, '@type': ['http://www.w3.org/2002/07/owl#Class'],
            LABEL: [{'@value': 'Person', '@language': 'en'},
                    {'@value': 'Personne', '@language': 'fr'}],
            DEFINITION: [{'@value': 'A person.'}],
            ALIAS: [{'@value': 'Human'}, {'@value': 'Person'}],
        }, {'@id': '_:restriction', '@type': ['http://www.w3.org/2002/07/owl#Restriction']}])

    provider = provider_with(handle, server_version='4.4.1')
    source = provider.initialize()
    assert source.revision.endswith('#production') and source.library_version == '4.4.1'
    assert source.sha256 is None
    entity = provider.get_entity('ex:Person')
    assert entity.identifier == IRI and entity.label == 'Person'
    assert entity.definition == 'A person.' and entity.aliases == ('Human',)
    assert len(entity.types) == 1
    provider.revision = 'different-commit'
    provider.branch_id = 'different-branch'
    assert provider.resolve(IRI).candidates == (entity,)
    assert len(requests) == 2
    assert all('/entities/' in r.url.path for r in requests)
    provider.close()
    assert not provider._client.is_closed  # Caller owns the injected client.
    provider._client.close()


def test_production_selection_and_deferred_operations_never_send_requests():
    def forbidden(request):
        pytest.fail('Deferred operations must not guess endpoints or versions')

    client = httpx.Client(transport=httpx.MockTransport(forbidden))
    provider = MobiOntologyProvider('https://mobi.example/mobirest', 'record', client=client)
    with pytest.raises(OntologyUnsupportedError, match='production branch_id'):
        provider.initialize()
    for operation in (
        lambda: provider.search('Person'), lambda: provider.resolve('Person'),
        lambda: provider.neighborhood([IRI]),
        lambda: provider.query_sparql('DELETE WHERE {?s ?p ?o}'),
    ):
        with pytest.raises(OntologyUnsupportedError):
            operation()
    client.close()


@pytest.mark.parametrize('status', [401, 403, 404, 500, 302])
def test_http_errors_are_not_false_missing_entities_or_exposed_bodies(status):
    def handle(request):
        return httpx.Response(status, text='private server details')

    provider = provider_with(handle)
    with pytest.raises(OntologyQueryError, match=f'HTTP {status}') as error:
        provider.resolve(IRI)
    assert 'private server details' not in str(error.value)
    provider._client.close()


def test_import_scope_and_moving_revision_selectors_are_explicit():
    def forbidden(request):
        pytest.fail('Initialization must not use edit-inclusive metadata endpoints')

    provider = provider_with(forbidden)
    assert 'imports are excluded' in provider.initialize().warnings[0]
    provider._client.close()
    imports = provider_with(forbidden, include_imports=True)
    assert 'not verified' in imports.initialize().warnings[0]
    imports._client.close()
    strict = provider_with(forbidden, include_imports=True)
    strict._settings.unresolved_imports = 'error'
    with pytest.raises(OntologyUnsupportedError, match='committed-only import API'):
        strict.initialize()
    strict._client.close()
    moving = provider_with(forbidden)
    moving.revision = 'head'
    with pytest.raises(OntologyUnsupportedError, match='fixed commit IRI'):
        moving.initialize()
    moving._client.close()


def test_missing_entity_statements_and_unsupported_jsonld_are_explicit():
    responses = iter([[], {'@context': {'label': LABEL}, '@id': IRI, 'label': 'Person'}])

    def handle(request):
        return httpx.Response(200, json=next(responses))

    provider = provider_with(handle, include_imports=False)
    result = provider.resolve(IRI)
    assert result.status == 'not_found' and not result.candidates
    with pytest.raises(OntologyUnsupportedError, match='Compact JSON-LD'):
        provider.get_entity(IRI)
    provider._client.close()


def test_transport_and_invalid_json_errors_are_domain_errors():
    def handle(request):
        return httpx.Response(200, text='not JSON')

    provider = provider_with(handle)
    with pytest.raises(OntologyQueryError, match='invalid JSON'):
        provider.get_entity(IRI)
    provider._client.close()

    def unavailable(request):
        raise httpx.ConnectError('private transport details', request=request)

    provider = provider_with(unavailable)
    with pytest.raises(OntologyQueryError) as error:
        provider.get_entity(IRI)
    assert 'private transport details' not in str(error.value)
    provider._client.close()
