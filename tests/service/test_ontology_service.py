"""Native OWL/RDF access and workflow-facing contracts using RDFLib 7.6.0."""

import asyncio
import json
from pathlib import Path
from threading import get_ident

from langchain_core.messages import ToolMessage

import pytest
from pydantic import ValidationError
from rdflib import Graph

from graphrag.config.graph_rag_config import GraphDataProfile, GraphRagSettings
from graphrag.config.ontology_config import OntologySettings
from graphrag.model.ontology import (
    OntologyAmbiguityError, OntologyContext, OntologyContextLimits,
    OntologyLoadError, OntologyNotFoundError, OntologyQueryError, OntologyUnsupportedError,
)
from graphrag.service.ontology_service import OntologyService, create_ontology_tools

EX = 'http://example.org/test/'
RDFS = 'http://www.w3.org/2000/01/rdf-schema#'
RDF = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
OWL_NS = 'http://www.w3.org/2002/07/owl#'

OWL = '''@prefix EX: <http://example.org/test/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix IAO: <http://purl.obolibrary.org/obo/IAO_> .
@prefix oboInOwl: <http://www.geneontology.org/formats/oboInOwl#> .
<http://example.org/ontology> a owl:Ontology .
EX:Entity a owl:Class ; rdfs:label "Entity" .
EX:Organization a owl:Class ; rdfs:label "Organization" ;
 IAO:0000115 "An organization is a group of people with a shared purpose." ;
 oboInOwl:hasExactSynonym "Institution", "Shared" ; rdfs:subClassOf EX:Entity .
EX:Company a owl:Class ; rdfs:label "Company" ;
 oboInOwl:hasExactSynonym "Shared" ; rdfs:subClassOf EX:Organization .
EX:Person a owl:Class ; rdfs:label "Person" ; rdfs:subClassOf EX:Entity,
 [ a owl:Restriction ; owl:onProperty EX:worksFor ; owl:someValuesFrom EX:Organization ] .
EX:CycleA a owl:Class ; rdfs:subClassOf EX:CycleB .
EX:CycleB a owl:Class ; rdfs:subClassOf EX:CycleA .
EX:worksFor a owl:ObjectProperty ; rdfs:label "works for" ;
 rdfs:domain EX:Person ; rdfs:range EX:Organization .
EX:alice a owl:NamedIndividual, EX:Person ; rdfs:label "Alice" ; EX:worksFor EX:acme .
EX:acme a owl:NamedIndividual, EX:Company ; rdfs:label "Acme" .
'''


@pytest.fixture
def service(tmp_path: Path) -> OntologyService:
    path = tmp_path / 'ontology.ttl'
    path.write_text(OWL)
    return OntologyService.from_profile(GraphDataProfile(version='1', ontology=OntologySettings(path=path)))


def triples(result) -> set[tuple[str, str, str]]:
    return {(edge.subject, edge.predicate, edge.object) for edge in result.relationships}


def test_metadata_resolution_search_and_source(service: OntologyService) -> None:
    source = service.initialize()
    assert source.library_version == '7.6.0'
    assert len(source.sha256) == 64
    assert Path(source.path).read_text() == OWL
    entity = service.get_entity('EX:Organization')
    assert entity.identifier == EX + 'Organization'
    assert entity.label == 'Organization'
    assert entity.definition.startswith('An organization')
    assert entity.types == (OWL_NS + 'Class',)
    assert entity.aliases == ('Institution', 'Shared')
    assert service.get_entity(entity.identifier) == entity
    assert service.resolve_entity('institution') == entity
    assert service.search('NSTIT').entities == (entity,)
    assert service.search('NSTIT', exact=True).total_matches == 0
    assert service.search('EX:Organization', exact=True).entities == (entity,)
    assert service.search('.*').total_matches == 0
    assert service.get_entity('EX:Company').definition is None
    assert set(service.get_entity('EX:alice').types) == {OWL_NS + 'NamedIndividual', EX + 'Person'}


def test_ambiguity_and_unknown_terms_are_explicit(service: OntologyService) -> None:
    result = service.resolve('Shared', limit=1)
    assert result.status == 'ambiguous'
    assert result.total_matches == 2 and result.truncated
    with pytest.raises(OntologyAmbiguityError) as error:
        service.resolve_entity('Shared')
    assert error.value.resolution.total_matches == 2
    assert service.resolve('missing').status == 'not_found'
    with pytest.raises(OntologyNotFoundError):
        service.get_entity('EX:missing')
    with pytest.raises(OntologyNotFoundError):
        service.resolve_entity('missing')


def test_hierarchy_cycles_direction_and_unknown_properties(service: OntologyService) -> None:
    parents = service.ancestors('EX:Company')
    assert triples(parents) == {
        (EX + 'Company', RDFS + 'subClassOf', EX + 'Organization'),
        (EX + 'Organization', RDFS + 'subClassOf', EX + 'Entity'),
    }
    assert len(service.ancestors('EX:CycleA').relationships) == 2
    assert (EX + 'Person', RDFS + 'subClassOf', EX + 'Entity') in triples(service.descendants('EX:Entity'))
    assert triples(service.relationships('EX:acme', direction='incoming', predicates=['EX:worksFor'])) == {
        (EX + 'alice', EX + 'worksFor', EX + 'acme'),
    }
    assert not service.relationships('EX:Person', predicates=['EX:worksFor']).relationships
    assert (EX + 'worksFor', RDFS + 'domain', EX + 'Person') in triples(service.relationships('EX:worksFor'))


def test_context_preserves_original_restrictions_and_literals(service: OntologyService) -> None:
    context = service.get_context(['Person'])
    edges = context.neighborhood.relationships
    restriction = next(edge.object for edge in edges if edge.subject == EX + 'Person'
                       and edge.predicate == RDFS + 'subClassOf' and edge.object_kind == 'blank_node')
    assert (restriction, OWL_NS + 'onProperty', EX + 'worksFor') in triples(context.neighborhood)
    assert (restriction, OWL_NS + 'someValuesFrom', EX + 'Organization') in triples(context.neighborhood)
    assert (EX + 'Person', EX + 'worksFor', EX + 'Organization') not in triples(context.neighborhood)
    assert any(edge.object_kind == 'literal' and edge.object == 'Person' for edge in edges)
    assert context == service.get_context(['Person'])  # Stable IDs within a question.
    assert OntologyContext.model_validate_json(context.model_dump_json()) == context


def test_context_limits_apply_to_metadata_literals_and_resolution(service: OntologyService) -> None:
    limits = OntologyContextLimits(max_depth=1, max_entities=3, max_relationships=2, max_candidates=1,
                                   max_definition_chars=12, max_label_chars=8, max_aliases=0, max_literal_chars=5)
    context = service.get_context(['Institution', 'Shared', 'missing'], limits=limits)
    assert context.neighborhood.seed_ids == (EX + 'Organization',)
    assert [r.status for r in context.resolutions] == ['resolved', 'ambiguous', 'not_found']
    assert len(context.neighborhood.entities) <= 3
    assert len(context.neighborhood.relationships) <= 2
    for entity in (*context.neighborhood.entities, *(r.candidates[0] for r in context.resolutions if r.candidates)):
        assert entity.definition is None or len(entity.definition) <= 12
        assert entity.label is None or len(entity.label) <= 8
        assert not entity.aliases
    assert all(len(edge.object) <= 5 for edge in context.neighborhood.relationships if edge.object_kind == 'literal')
    assert 'resolution candidates truncated' in context.warnings
    assert 'sha256' in context.to_structured_text()
    assert not service.get_context(['missing']).neighborhood.entities


def test_depth_empty_filters_and_zero_relationship_budget(service: OntologyService) -> None:
    one = service.ancestors('EX:Company', limits=OntologyContextLimits(max_depth=1))
    assert len(one.relationships) == 1
    assert 'max_depth' in one.truncation_reasons
    assert not service.neighborhood(['EX:Company'], predicates=[]).relationships
    zero = service.neighborhood(['EX:Company'], limits=OntologyContextLimits(max_relationships=0))
    assert not zero.relationships and 'max_relationships' in zero.truncation_reasons
    small = service.neighborhood(['EX:Company', 'EX:Person'], limits=OntologyContextLimits(max_entities=1))
    assert len(small.entities) == 1 and 'max_entities' in small.truncation_reasons


def test_new_question_refresh_preserves_active_snapshot(service: OntologyService) -> None:
    original = service.for_question()
    assert original is service
    source = original.initialize()
    path = Path(source.path)
    path.write_text(OWL.replace('"Organization"', '"New label"'))
    assert original.get_entity('EX:Organization').label == 'Organization'
    updated = original.for_question()
    assert updated is not original
    assert updated.get_entity('EX:Organization').label == 'New label'
    assert updated.initialize().sha256 != source.sha256
    assert updated.for_question() is updated
    path.write_text('invalid ontology')
    with pytest.raises(OntologyLoadError):
        updated.for_question()
    assert updated.get_entity('EX:Organization').label == 'New label'


@pytest.mark.parametrize('suffix,format_name', [('.owl', None), ('.rdf', 'xml'), ('.bin', 'xml'), ('.nt', 'nt'), ('.n3', 'n3')])
def test_native_parser_format_selection(tmp_path: Path, suffix: str, format_name: str | None) -> None:
    path = tmp_path / ('ontology' + suffix)
    Graph().parse(data=OWL, format='turtle').serialize(destination=path, format=format_name or 'xml', encoding='utf-8')
    contents = path.read_bytes()
    reader = OntologyService(OntologySettings(path=path, format=format_name))
    assert reader.resolve_entity('Institution').identifier == EX + 'Organization'
    assert len(reader.ancestors(EX + 'Company').relationships) == 2
    assert path.read_bytes() == contents


def test_owlxml_requires_rdf_export(tmp_path: Path) -> None:
    path = tmp_path / 'ontology.owl'
    path.write_text('<Ontology xmlns="http://www.w3.org/2002/07/owl#"/>')
    with pytest.raises(OntologyLoadError, match='OWL/XML'):
        OntologyService(OntologySettings(path=path)).initialize()


def test_local_import_closure_and_refresh(tmp_path: Path) -> None:
    root, imported = tmp_path / 'root.ttl', tmp_path / 'import.ttl'
    root.write_text('@prefix owl: <http://www.w3.org/2002/07/owl#> . <http://example.org/root> owl:imports <http://example.org/import> .')
    imported.write_text(OWL + '<http://example.org/ontology> owl:imports <http://example.org/root> .')
    reader = OntologyService(OntologySettings(path=root, imports={'http://example.org/import': imported, 'http://example.org/root': root}))
    source = reader.initialize()
    assert len(source.imported_files) == 1
    assert not source.warnings and reader.for_question() is reader
    imported.write_text(OWL.replace('"Organization"', '"New label"'))
    updated = reader.for_question()
    assert reader.get_entity('EX:Organization').label == 'Organization'
    assert updated.get_entity('EX:Organization').label == 'New label'
    assert updated.initialize().sha256 == source.sha256
    assert updated.initialize().imported_files[0].sha256 != source.imported_files[0].sha256
    imported.unlink()
    with pytest.raises(OntologyLoadError):
        updated.for_question()


def test_unmapped_imports_are_explicit(tmp_path: Path) -> None:
    path = tmp_path / 'ontology.ttl'
    path.write_text(OWL + '<http://example.org/ontology> owl:imports <https://remote.example/ontology> .')
    settings = OntologySettings(path=path)
    reader = OntologyService(settings)
    assert reader.initialize().warnings == ('Ontology import was not loaded: https://remote.example/ontology',)
    assert reader.get_context(['Company']).warnings
    with pytest.raises(OntologyLoadError, match='import was not loaded'):
        OntologyService(settings.model_copy(update={'unresolved_imports': 'error'})).initialize()


def test_configurable_annotations_language_and_native_prefixes(tmp_path: Path) -> None:
    path = tmp_path / 'ontology.ttl'
    path.write_text('''@prefix d: <http://example.org/domain/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
d:Org rdfs:label "Organisation"@fr, "Organization"@en, "Default" ;
 skos:definition "Shared purpose"@en ; skos:altLabel "Institution" ;
 d:description "Custom definition" ; d:display "Custom label" .''')
    settings = OntologySettings(path=path, prefixes={'D': 'http://example.org/domain/'})
    reader = OntologyService(settings)
    entity = reader.get_entity('D:Org')
    assert entity.identifier == 'http://example.org/domain/Org'
    assert entity.label == 'Organization' and entity.definition == 'Shared purpose'
    assert entity.aliases == ('Institution',)
    assert OntologyService(settings.model_copy(update={'language': 'fr'})).get_entity('D:Org').label == 'Organisation'
    assert OntologyService(settings.model_copy(update={'language': 'de'})).get_entity('D:Org').label == 'Default'
    custom = OntologyService(settings.model_copy(update={'label_predicates': ('D:display',), 'definition_predicates': ('D:description',)}))
    assert custom.get_entity('D:Org').label == 'Custom label'
    assert custom.get_entity('D:Org').definition == 'Custom definition'
    settings.prefixes['D'] = 'http://elsewhere.example/'
    assert reader.get_entity('D:Org') == entity


def test_literal_whitespace_language_and_datatype_are_preserved(tmp_path: Path) -> None:
    path = tmp_path / 'ontology.ttl'
    path.write_text(OWL + 'EX:Person EX:text "  spaced  "@en, ""; EX:count 7 .')
    reader = OntologyService(OntologySettings(path=path))
    edges = reader.relationships('EX:Person', predicates=['EX:text', 'EX:count']).relationships
    assert {edge.object for edge in edges} == {'  spaced  ', '', '7'}
    assert next(edge for edge in edges if edge.object == '7').datatype == 'http://www.w3.org/2001/XMLSchema#integer'
    assert next(edge for edge in edges if edge.object == '  spaced  ').language == 'en'


def test_native_sparql_json_result_bounds_and_terms(service: OntologyService) -> None:
    result = service.query_sparql('''SELECT ?entity ?text ?number ?unbound WHERE {
 VALUES (?entity ?text ?number ?unbound) {
  (EX:alice "Alice"@en 7 UNDEF) (EX:acme "Acme"@en 8 UNDEF)
 }} ORDER BY ?number''', limit=1)
    assert result.query_type == 'SELECT' and result.truncated
    assert result.data['head']['vars'] == ['entity', 'text', 'number', 'unbound']
    rows = result.data['results']['bindings']
    assert len(rows) == 1
    assert rows[0]['entity'] == {'type': 'uri', 'value': EX + 'alice'}
    assert rows[0]['text']['xml:lang'] == 'en'
    assert rows[0]['number']['datatype'] == 'http://www.w3.org/2001/XMLSchema#integer'
    assert 'unbound' not in rows[0]
    assert type(result).model_validate_json(result.model_dump_json()) == result
    assert service.query_sparql('SELECT ?s WHERE {?s EX:missing ?o}').data['results']['bindings'] == []
    assert service.query_sparql('SELECT * WHERE {}').data['results']['bindings'] == [{}]


def test_anonymous_axioms_are_queryable_without_projection(service: OntologyService) -> None:
    result = service.query_sparql('SELECT ?expression WHERE {EX:Person rdfs:subClassOf ?expression . ?expression owl:onProperty EX:worksFor}')
    assert result.data['results']['bindings'][0]['expression']['type'] == 'bnode'


@pytest.mark.parametrize('query_type,query', [
    ('ASK', 'ASK {EX:Company rdfs:subClassOf EX:Organization}'),
    ('CONSTRUCT', 'CONSTRUCT {?s rdfs:label ?label} WHERE {?s rdfs:label ?label}'),
    ('DESCRIBE', 'DESCRIBE EX:Company'),
])
def test_other_native_read_query_forms(service: OntologyService, query_type: str, query: str) -> None:
    result = service.query_sparql(query, limit=1)
    assert result.query_type == query_type
    if query_type == 'ASK':
        assert result.data['boolean'] is True and not result.truncated
    else:
        assert len(Graph().parse(data=result.data, format='turtle')) == 1
        assert result.truncated


@pytest.mark.parametrize('query', [
    'SELECT ?s FROM <https://remote.example/ontology> WHERE {?s ?p ?o}',
    'SELECT ?s FROM NAMED <file:///tmp/ontology> WHERE {?s ?p ?o}',
    'SELECT ?s WHERE {SERVICE <https://remote.example/sparql> {?s ?p ?o}}',
    'SELECT ?s WHERE {{SELECT ?s WHERE {SERVICE SILENT <https://remote.example/sparql> {?s ?p ?o}}}}',
])
def test_external_sources_do_not_enter_snapshot_queries(service: OntologyService, monkeypatch: pytest.MonkeyPatch, query: str) -> None:
    service.initialize()
    def unexpected(*args, **kwargs):
        pytest.fail('External access reached query evaluation')
    monkeypatch.setattr(Graph, 'query', unexpected)
    with pytest.raises(OntologyUnsupportedError):
        service.query_sparql(query)


def test_query_errors_and_updates_do_not_change_snapshot(service: OntologyService) -> None:
    source = service.initialize()
    for query in ('SELECT invalid', 'DELETE WHERE {?s ?p ?o}'):
        with pytest.raises(OntologyQueryError):
            service.query_sparql(query)
    assert service.initialize() == source
    assert service.get_entity('EX:Organization').label == 'Organization'


def test_invalid_configuration_arguments_and_retry(tmp_path: Path, service: OntologyService) -> None:
    with pytest.raises(OntologyLoadError):
        OntologyService.from_profile(GraphDataProfile(version='1'))
    path = tmp_path / 'retry.ttl'
    reader = OntologyService(OntologySettings(path=path))
    with pytest.raises(OntologyLoadError):
        reader.initialize()
    path.write_text(OWL)
    assert reader.resolve_entity('Company').identifier == EX + 'Company'
    with pytest.raises(ValidationError):
        OntologyContextLimits(max_depth=-1)
    for call in (lambda: service.resolve(' '), lambda: service.search('x', limit=0),
                 lambda: service.get_context('Company'), lambda: service.get_context(['Company'] * 21),
                 lambda: service.neighborhood(['Company'], direction='sideways'),
                 lambda: service.query_sparql('ASK {}', limit=201)):
        with pytest.raises(ValueError):
            call()


def test_nested_profile_environment(service: OntologyService, monkeypatch: pytest.MonkeyPatch) -> None:
    source = service.initialize()
    monkeypatch.setenv('GRAPH_RAG_DATA_PROFILE__VERSION', '1')
    monkeypatch.setenv('GRAPH_RAG_DATA_PROFILE__ONTOLOGY__PATH', source.path)
    settings = GraphRagSettings(
        _env_file=None, llm_url='https://llm.example.test/v1', llm_api_key='secret',
        llm_model='test', llm_provider='test', graph_db_mcp_url='https://graph.example.test/mcp',
        graph_db_username='neo4j', graph_db_password='secret', graph_db_database='neo4j',
    )
    assert OntologyService.from_profile(settings.data_profile).resolve_entity('Company').identifier == EX + 'Company'


def test_langchain_ontology_tools_expose_validated_schemas_and_payloads(service: OntologyService) -> None:
    tools = {tool.name: tool for tool in create_ontology_tools(service)}
    assert set(tools) == {'ontology_search', 'ontology_context', 'ontology_sparql'}
    schema = tools['ontology_context'].get_input_schema().model_json_schema()
    assert set(schema['properties']) == {'terms', 'direction', 'predicates', 'limits'}
    assert schema['properties']['terms']['maxItems'] == 20
    hits = tools['ontology_search'].invoke({'query': 'Institution', 'limit': 1})
    assert hits['entities'][0]['identifier'] == EX + 'Organization'
    assert tools['ontology_sparql'].invoke({'query': 'ASK {EX:Company a owl:Class}'})['data']['boolean'] is True
    context = tools['ontology_context'].invoke({
        'terms': ['Shared', 'missing', 'Institution'],
        'limits': {'max_depth': 1, 'max_relationships': 1},
    })
    assert [resolution['status'] for resolution in context['resolutions']] == ['ambiguous', 'not_found', 'resolved']
    assert len(context['neighborhood']['relationships']) <= 1
    assert context['source']['sha256'] == service.initialize().sha256


def test_langchain_tool_call_returns_json_tool_message(service: OntologyService) -> None:
    tool = next(tool for tool in create_ontology_tools(service) if tool.name == 'ontology_context')
    message = tool.invoke({
        'type': 'tool_call', 'name': tool.name, 'id': 'ontology-call-1',
        'args': {'terms': ['Institution']},
    })
    assert isinstance(message, ToolMessage)
    assert message.tool_call_id == 'ontology-call-1' and message.status == 'success'
    assert isinstance(message.content, str)
    payload = json.loads(message.content)
    assert payload['resolutions'][0]['candidates'][0]['identifier'] == EX + 'Organization'
    assert payload['source']['sha256'] == service.initialize().sha256


@pytest.mark.parametrize('tool_name,arguments', [
    ('ontology_search', {'query': 'Thing', 'limit': 0}),
    ('ontology_search', {'query': ' '}),
    ('ontology_context', {'terms': []}),
    ('ontology_context', {'terms': ['Person'], 'direction': 'sideways'}),
    ('ontology_context', {'terms': ['Person'], 'limits': {'max_depth': -1}}),
    ('ontology_sparql', {'query': 'ASK {}', 'limit': 201}),
])
def test_langchain_validation_errors_are_agent_observations(service: OntologyService, tool_name: str, arguments: dict) -> None:
    tool = next(tool for tool in create_ontology_tools(service) if tool.name == tool_name)
    message = tool.invoke({'type': 'tool_call', 'name': tool.name, 'id': 'invalid-call', 'args': arguments})
    assert isinstance(message, ToolMessage) and message.status == 'error'
    assert isinstance(message.content, str) and message.content.startswith('Invalid ontology tool arguments:')


def test_langchain_query_errors_are_agent_observations(service: OntologyService) -> None:
    tool = next(tool for tool in create_ontology_tools(service) if tool.name == 'ontology_sparql')
    for query in ('SELECT invalid', 'DELETE WHERE {?s ?p ?o}', 'ASK {SERVICE <https://example.test> {?s ?p ?o}}'):
        message = tool.invoke({'type': 'tool_call', 'name': tool.name, 'id': 'failed-query', 'args': {'query': query}})
        assert isinstance(message, ToolMessage) and message.status == 'error'
        assert isinstance(message.content, str) and message.content.startswith(('OntologyQueryError:', 'OntologyUnsupportedError:'))
    assert service.get_entity('EX:Organization').label == 'Organization'


def test_langchain_tools_remain_bound_to_question_snapshot(service: OntologyService) -> None:
    original = service.for_question()
    original_tools = {tool.name: tool for tool in create_ontology_tools(original)}
    original_context = original_tools['ontology_context'].invoke({'terms': ['Institution']})
    Path(original.initialize().path).write_text(OWL.replace('"Organization"', '"Updated label"'))
    unchanged_context = original_tools['ontology_context'].invoke({'terms': ['Institution']})
    assert unchanged_context == original_context
    refreshed = original.for_question()
    refreshed_tools = {tool.name: tool for tool in create_ontology_tools(refreshed)}
    new_context = refreshed_tools['ontology_context'].invoke({'terms': ['Institution']})
    assert new_context['resolutions'][0]['candidates'][0]['label'] == 'Updated label'
    assert new_context['source']['sha256'] != original_context['source']['sha256']


def test_langchain_async_tool_invocation_uses_worker_thread(service: OntologyService, monkeypatch: pytest.MonkeyPatch) -> None:
    caller_thread = get_ident()
    execution_threads: list[int] = []
    original_context = service.get_context

    def tracked_context(*args, **kwargs):
        execution_threads.append(get_ident())
        return original_context(*args, **kwargs)

    monkeypatch.setattr(service, 'get_context', tracked_context)
    tool = next(tool for tool in create_ontology_tools(service) if tool.name == 'ontology_context')
    result = asyncio.run(tool.ainvoke({'terms': ['Institution']}))
    assert result['resolutions'][0]['status'] == 'resolved'
    assert len(execution_threads) == 1 and execution_threads[0] != caller_thread
