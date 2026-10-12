"""Provider substitution, semantic alignment and question-snapshot integration."""

from pathlib import Path

import pytest
import yaml

from graphrag.config.ontology_config import OntologySettings
from graphrag.model.ontology import (
    OntologyContextLimits,
    OntologyLoadError,
    OntologyUnsupportedError,
)
from graphrag.model.ontology_mapping import OntologyDatabaseContext, SchemaMappings
from graphrag.model.resource import Resource
from graphrag.ontology.base_providers import OntologyProvider
from graphrag.ontology.linkml_loader import load_linkml_mappings
from graphrag.ontology.mobi_provider import MobiOntologyProvider
from graphrag.ontology.rdflib_provider import RDFLibOntologyProvider
from graphrag.ontology.resources import OntologyResources
from graphrag.service.ontology_service import OntologyService, create_ontology_tools

EX = "https://example.org/ontology/"


@pytest.fixture
def resources(tmp_path):
    ontology = tmp_path / "ontology.ttl"
    ontology.write_text("""@prefix ex: <https://example.org/ontology/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
ex:Incident a owl:Class ; rdfs:label "Incident" .
ex:Other a owl:Class ; rdfs:label "Shared" .
ex:Another a owl:Class ; rdfs:label "Shared" .
ex:Attack a owl:Class ; rdfs:label "Attack" .
ex:hasAttackType a owl:ObjectProperty ; rdfs:domain ex:Incident ; rdfs:range ex:Attack .
ex:year a owl:DatatypeProperty .
""")
    schema = tmp_path / "schema.yaml"
    schema.write_text("""id: https://example.org/schema
name: test_graph
prefixes:
  linkml: https://w3id.org/linkml/
  ex: https://example.org/ontology/
imports: [linkml:types]
classes:
  Event:
    close_mappings: [ex:Incident]
    annotations:
      neo4j_label: Event
      mapping_status: proposed
      mapping_provenance: Test alignment review
    attributes:
      year:
        range: integer
        slot_uri: ex:year
        annotations:
          neo4j_property: year
      attack_types:
        range: AttackType
        multivalued: true
        exact_mappings: [ex:hasAttackType]
        annotations:
          neo4j_relationship: IS_OF_ATTACKTYPE
          neo4j_direction: outgoing
          neo4j_source_label: Event
          neo4j_target_label: AttackType
  AttackType:
    class_uri: ex:Attack
    annotations:
      neo4j_label: AttackType
""")
    return ontology, schema


def mapped(
    data,
    uris,
):
    return tuple(
        data.mappings[i]
        for i in sorted({i for uri in uris for i in data.ontology_index.get(uri, ())})
    )


def make_service(resources):
    ontology, schema = resources
    return OntologyService(OntologySettings(path=ontology, schema_path=schema))


def test_combined_meaning_graph_structure_and_provenance(resources):
    service = make_service(resources)
    result = service.describe(["Incident"])
    incident = next(m for m in result.mappings if m.ontology_uri == EX + "Incident")
    assert incident.status == "proposed" and incident.relation == "close"
    node = incident.schema_elements[0]
    assert node.identifier == "Event"
    schema = node.representation["schema"]
    assert schema["attributes"]["year"]["range"] == "integer"
    annotations = schema["attributes"]["attack_types"]["annotations"]
    assert tuple(
        annotations["neo4j_" + key]["value"]
        for key in ("source_label", "relationship", "target_label", "direction")
    ) == (
        "Event",
        "IS_OF_ATTACKTYPE",
        "AttackType",
        "outgoing",
    )
    property_mapping = next(
        m for m in result.mappings if m.ontology_uri == EX + "hasAttackType"
    )
    assert (
        property_mapping.status == "asserted" and property_mapping.relation == "exact"
    )
    assert property_mapping.schema_elements[0].schema_slot == "attack_types"
    assert len(result.schema_sources) == 1 and all(
        len(s.sha256) == 64 for s in result.schema_sources
    )
    assert any("not been verified" in w for w in result.warnings)
    assert OntologyDatabaseContext.model_validate_json(result.model_dump_json()) == result


def test_reverse_labels_properties_and_relationships(resources):
    service = make_service(resources)
    assert (
        service.resolve_database_element("Event").mappings[0].ontology_uri
        == EX + "Incident"
    )
    assert (
        service.resolve_database_element("Event", property_name="year")
        .mappings[0]
        .ontology_uri
        == EX + "year"
    )
    result = service.resolve_database_element(
        "Event", relationship_type="IS_OF_ATTACKTYPE"
    )
    assert [m.ontology_uri for m in result.mappings] == [EX + "hasAttackType"]
    assert result.ontology.resolutions[0].status == "resolved"
    assert not service.resolve_database_element("event").mappings
    with pytest.raises(ValueError):
        service.resolve_database_element(
            "Event", property_name="year", relationship_type="IS_OF_ATTACKTYPE"
        )


def test_no_implicit_name_alignment_and_ambiguity(resources):
    service = make_service(resources)
    for term in ["Shared", "missing"]:
        assert not service.describe([term]).mappings
    assert (
        service.describe(["Shared"]).ontology.resolutions[0].status == "ambiguous"
    )
    ontology, schema = resources
    raw = yaml.safe_load(schema.read_text())
    raw["classes"]["Event"].pop("close_mappings")
    schema.write_text(yaml.safe_dump(raw))
    unaligned_service = OntologyService(
        OntologySettings(path=ontology, schema_path=schema)
    )
    assert (
        EX + "Incident"
        in unaligned_service.describe(["Incident"]).unmapped_ontology_uris
    )
    no_mapping_provider = OntologyService(OntologySettings(path=ontology))
    assert (
        "No database schema mappings configured"
        in no_mapping_provider.describe(["Incident"]).warnings
    )
    assert not no_mapping_provider.resolve_database_element("Event").mappings


def test_independent_providers_and_mobi_deferred_operations(resources):
    ontology, schema = resources
    file_loader = OntologyResources(str(ontology))

    class AlternateLoader(OntologyResources):
        def __init__(self):
            super().__init__(str(ontology))

        """A byte source with no parsing or query methods."""

        def get_resource(self):
            return file_loader.get_resource()

        def get_import(
            self,
            ontology_iri,
        ):
            return file_loader.get_import(ontology_iri)

    alternate = AlternateLoader()
    service = OntologyService(
        provider=RDFLibOntologyProvider(alternate),
        schema_mappings=load_linkml_mappings(schema),
    )
    assert service.describe(["Incident"]).mappings
    assert service.query_sparql("ASK { ex:Incident a owl:Class }").data["boolean"]
    mobi = MobiOntologyProvider("https://mobi.example.org", "record-id", "revision-id")
    service = OntologyService(provider=mobi)
    with pytest.raises(OntologyUnsupportedError, match="production branch_id"):
        service.initialize()
    with pytest.raises(OntologyUnsupportedError, match="SPARQL is pending"):
        service.query_sparql("ASK {}")


def test_initialized_mapping_ignores_schema_changes(resources):
    service = make_service(resources)
    old = service.describe(["Incident"])
    _ontology, schema = resources
    raw = yaml.safe_load(schema.read_text())
    raw["classes"]["Event"]["annotations"]["mapping_status"] = "verified"
    raw["classes"]["Event"]["attributes"]["year"]["annotations"][
        "neo4j_property"
    ] = "iyear"
    schema.write_text(yaml.safe_dump(raw))
    assert service.describe(["Incident"]) == old
    schema.unlink()
    assert service.describe(["Incident"]) == old
    assert not hasattr(service._mapping_data, "for_question")


def test_invalid_mapping_metadata_endpoints_and_import_errors_fail_early(
    resources,
    monkeypatch,
):
    _ontology, schema = resources
    raw = yaml.safe_load(schema.read_text())
    raw["classes"]["Event"]["annotations"]["mapping_status"] = "invalid-status"
    schema.write_text(yaml.safe_dump(raw))
    with pytest.raises(OntologyLoadError, match="status"):
        make_service(resources).initialize()
    raw["classes"]["Event"]["annotations"]["mapping_status"] = "proposed"
    schema.write_text(yaml.safe_dump(raw))
    schema.write_text(
        schema.read_text().replace(
            "neo4j_target_label: AttackType", "neo4j_target_label: Wrong"
        )
    )
    with pytest.raises(OntologyLoadError, match="Conflicting graph"):
        make_service(resources).initialize()
    schema.write_text(
        "id: https://example.org/schema\nname: remote\nimports: [https://example.org/remote]\n"
    )
    from linkml_runtime.utils.schemaview import SchemaView

    def unavailable_import(
        self,
        imp,
        from_schema=None,
    ):
        assert imp == "https://example.org/remote"
        raise OSError("Import transport unavailable")

    monkeypatch.setattr(SchemaView, "load_import", unavailable_import)
    with pytest.raises(OntologyLoadError, match="Import transport unavailable"):
        make_service(resources).initialize()


def test_local_imports_inheritance_and_snapshot(
    resources,
    monkeypatch,
):
    from graphrag.resource_loader import ResourceLoader

    reads = []
    original_read = ResourceLoader.read

    def track_read(
        self,
        uri,
        **kwargs,
    ):
        reads.append(uri)
        return original_read(self, uri, **kwargs)

    monkeypatch.setattr(ResourceLoader, "read", track_read)
    _, schema = resources
    parent = schema.parent / "parent.yaml"
    raw = yaml.safe_load(schema.read_text())
    parent.write_text(schema.read_text())
    child = {k: v for k, v in raw.items() if k != "classes"}
    child["imports"] = ["parent"]
    child["classes"] = {
        "ChildEvent": {"is_a": "Event", "annotations": {"neo4j_label": "Event"}}
    }
    schema.write_text(yaml.safe_dump(child))
    provider = load_linkml_mappings(schema)
    assert len(provider.sources) == 2
    assert mapped(provider, [EX + "year"])
    assert reads == [schema]  # LinkML alone reads parent.yaml.
    assert provider.sources[1].revision is None
    assert provider.sources[1].sha256 is None
    old = mapped(provider, [EX + "hasAttackType"])
    parent.write_text(parent.read_text().replace("IS_OF_ATTACKTYPE", "HAS_ATTACK_TYPE"))
    assert mapped(provider, [EX + "hasAttackType"]) == old
    parent.unlink()
    schema.unlink()
    assert mapped(provider, [EX + "hasAttackType"]) == old
    assert reads == [schema]


def test_incoming_relationship_direction(resources):
    _, schema = resources
    raw = yaml.safe_load(schema.read_text())
    slot = raw["classes"]["Event"]["attributes"].pop("attack_types")
    slot["range"] = "Event"
    slot["annotations"]["neo4j_direction"] = "incoming"
    raw["classes"]["AttackType"]["attributes"] = {"events": slot}
    schema.write_text(yaml.safe_dump(raw))
    result = make_service(resources).resolve_database_element(
        "AttackType", relationship_type="IS_OF_ATTACKTYPE"
    )
    edge = result.mappings[0].schema_elements[0]
    assert (
        edge.representation["binding"]["direction"] == "incoming"
        and edge.representation["binding"]["source_label"] == "Event"
        and edge.representation["binding"]["target_label"] == "AttackType"
    )


def test_combined_agent_tools(resources):
    service = make_service(resources)
    tools = {t.name: t for t in create_ontology_tools(service)}
    assert set(tools) == {
        "ontology_search", "ontology_context", "ontology_database_element",
        "ontology_relationships", "ontology_ancestors", "ontology_descendants",
    }
    result = tools["ontology_context"].invoke(
        {"terms": ["Incident", "ex:hasAttackType", "Shared", "missing"]}
    )
    assert (
        result["mappings"]
        and result["ontology"]["resolutions"][0]["status"] == "resolved"
    )
    assert [r["status"] for r in result["ontology"]["resolutions"]] == [
        "resolved", "resolved", "ambiguous", "not_found"
    ]
    binding = next(
        m for m in result["mappings"] if m["ontology_uri"] == EX + "hasAttackType"
    )["schema_elements"][0]["representation"]["binding"]
    assert binding["relationship"] == "IS_OF_ATTACKTYPE"
    assert binding["source_label"] == "Event"
    assert binding["target_label"] == "AttackType"
    result = tools["ontology_database_element"].invoke(
        {"element_name": "Event", "property_name": "year"}
    )
    assert result["mappings"][0]["ontology_uri"] == EX + "year"
    error = tools["ontology_database_element"].invoke(
        {"element_name": "Event", "property_name": "year", "relationship_type": "X"}
    )
    assert "ValueError" in error


def test_traversal_tools_pair_meaning_with_database_bindings(resources):
    ontology, _ = resources
    with ontology.open('a') as stream:
        stream.write('\nex:Incident rdfs:subClassOf ex:Attack .\n')
    tools = {tool.name: tool for tool in create_ontology_tools(make_service(resources))}
    for tool_name, term in (
        ('ontology_relationships', 'ex:hasAttackType'),
        ('ontology_ancestors', 'Incident'),
        ('ontology_descendants', 'Attack'),
    ):
        result = tools[tool_name].invoke({'term': term})
        assert result['ontology']['resolutions'][0]['status'] == 'resolved'
        assert result['schema_sources']
        bindings = {
            element['identifier']
            for mapping in result['mappings']
            for element in mapping['schema_elements']
        }
        assert {'Event', 'AttackType'} <= bindings
        if tool_name == 'ontology_relationships':
            assert 'IS_OF_ATTACKTYPE' in bindings


def test_downloaded_gtd_resources_end_to_end():
    root = Path(__file__).resolve().parents[2]
    base = root / "project-resources/gtd"
    service = make_service(
        (
            base / "ontology/gtdonto.ttl",
            base / "neo4j/schema.linkml.yaml",
        )
    )
    result = service.describe(["Incident"])
    incident = next(m for m in result.mappings if m.ontology_uri.endswith("#Incident"))
    assert incident.schema_elements[0].identifier == "Event"
    assert (
        len(
            [
                slot
                for slot in incident.schema_elements[0]
                .representation["schema"]["attributes"]
                .values()
                if "neo4j_property" in slot.get("annotations", {})
            ]
        )
        == 34
    )
    assert all(m.status == "proposed" for m in result.mappings)
    assert (
        service.resolve_database_element("Group", relationship_type="CARRIES_OUT")
        .mappings[0]
        .ontology_uri.endswith("#hasPerpGroup")
    )
    assert (
        service.query_sparql(
            "SELECT (COUNT(?c) AS ?count) WHERE { ?c a owl:Class }"
        ).data["results"]["bindings"][0]["count"]["value"]
        == "251"
    )


def test_abc_contracts_reject_incomplete_extensions():
    with pytest.raises(TypeError, match="abstract"):
        OntologyProvider()


def test_uri_loader_file_uri_and_in_memory_protocol(resources):
    import fsspec

    from graphrag.ontology.resources import OntologyResources

    ontology, _ = resources
    # A percent-encoded file URI goes through the same loader as a plain path.
    spaced = ontology.with_name("ontology with spaces.ttl")
    spaced.write_bytes(ontology.read_bytes())
    service = OntologyService(
        provider=RDFLibOntologyProvider(
            OntologyResources(spaced.as_uri(), format="turtle")
        )
    )
    assert service.resolve("Incident").candidates[0].identifier == EX + "Incident"
    uri = "memory://graphrag-tests/ontology.ttl"
    with fsspec.open(uri, "wb") as stream:
        stream.write(ontology.read_bytes())
    memory = OntologyService(
        provider=RDFLibOntologyProvider(OntologyResources(uri, format="turtle"))
    )
    assert memory.resolve("Incident").candidates[0].identifier == EX + "Incident"
    with fsspec.open(uri, "wb") as stream:
        stream.write(ontology.read_bytes().replace(b'"Incident"', b'"Updated"'))
    assert memory.resolve("Incident").status == "resolved"
    assert memory.resolve("Updated").status == "not_found"


def test_byte_loader_imports_and_rdflib_provider_configuration():
    from graphrag.config.ontology_config import OntologyReaderSettings

    root = b"""@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.org/root> a owl:Ontology ; owl:imports <https://example.org/import> ."""
    imported = b"""@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<https://example.org/ontology/Incident> rdfs:label "Incident" ."""

    class ExportLoader(OntologyResources):
        def __init__(self):
            super().__init__("https://mobi.example/export/root", format="turtle")

        def get_resource(self):
            return Resource(
                root,
                "https://mobi.example/export/root",
            )

        def get_import(
            self,
            ontology_iri,
        ):
            assert ontology_iri == "https://example.org/import"
            return Resource(
                imported,
                "https://mobi.example/export/import",
            )

    service = OntologyService(
        provider=RDFLibOntologyProvider(
            ExportLoader(),
            OntologyReaderSettings(unresolved_imports="error"),
        ),
    )
    source = service.initialize()
    assert source.sha256 is not None and source.imported_files[0].sha256 is not None
    assert service.resolve("Incident").status == "resolved"


def test_native_provider_does_not_retrieve_or_parse_rdf(
    resources,
    monkeypatch,
):
    from rdflib import Graph

    from graphrag.model.ontology import OntologySource, OntologySparqlResult

    ontology, schema = resources
    # Prepare a domain-contract fixture before prohibiting RDFLib parsing.
    context = OntologyService(OntologySettings(path=ontology)).get_context(["Incident"])
    native_source = OntologySource(
        path="https://mobi.example/records/test",
        revision="commit-123",
        library="mobi",
        library_version="4.4",
    )
    context = context.model_copy(update={"source": native_source})

    class NativeProvider(MobiOntologyProvider):
        def initialize(self):
            return native_source

        def resolve(self, term, **kwargs):
            assert term == "Incident"
            return context.resolutions[0]

        def neighborhood(self, identifiers, **kwargs):
            assert identifiers == [context.resolutions[0].candidates[0].identifier]
            return context.neighborhood

        def query_sparql(
            self,
            query,
            **kwargs,
        ):
            return OntologySparqlResult(
                source=native_source, query_type="ASK", data={"boolean": True}
            )

    def unexpected(
        *args,
        **kwargs,
    ):
        pytest.fail("Native backend must not parse an RDF export")

    monkeypatch.setattr(Graph, "parse", unexpected)
    service = OntologyService(
        provider=NativeProvider("https://mobi.example", "record", "commit-123"),
        schema_mappings=load_linkml_mappings(schema),
    )
    assert service.initialize().revision == "commit-123"
    assert service.query_sparql("ASK {}").data["boolean"]
    result = service.describe(["Incident"], limits=OntologyContextLimits(max_label_chars=3))
    assert result.mappings
    assert result.ontology.source == native_source
    assert result.ontology.resolutions[0].candidates[0].label == "Inc"
    assert "entity metadata truncated" in result.ontology.warnings
    assert "metadata" in result.ontology.neighborhood.truncation_reasons


def test_database_independent_mapping_with_a_relational_binding(resources):
    from graphrag.model.ontology_mapping import (
        DatabaseElement,
        OntologyDatabaseContext,
        OntologySchemaMapping,
    )

    ontology, _ = resources
    mapping = OntologySchemaMapping(
        ontology_uri=EX + "Incident",
        status="asserted",
        provenance="Relational schema alignment",
        schema_elements=(
            DatabaseElement(
                backend="postgresql",
                schema_class="IncidentTable",
                element_type="table",
                identifier="public.incidents",
                representation={
                    "table": "incidents",
                    "schema": "public",
                    "primary_key": ["incident_id"],
                },
            ),
        ),
    )

    data = SchemaMappings(
        mappings=(mapping,),
        database_index={("public.incidents", None, None): (0,)},
    )
    service = OntologyService(OntologySettings(path=ontology), schema_mappings=data)
    result = service.describe(["Incident"])
    element = result.mappings[0].schema_elements[0]
    assert element.backend == "postgresql" and "node_label" not in element.model_dump()
    assert (
        OntologyDatabaseContext.model_validate_json(result.model_dump_json()) == result
    )
    assert service.resolve_database_element("public.incidents").mappings == (mapping,)


def test_generic_graph_annotations_support_a_different_graph_backend(resources):
    _, schema = resources
    text = schema.read_text().replace("neo4j_", "graph_")
    raw = yaml.safe_load(text)
    raw["annotations"] = {"database_backend": "another_graph_database"}
    schema.write_text(yaml.safe_dump(raw))
    result = make_service(resources).describe(["Incident"])
    node = next(
        m for m in result.mappings if m.ontology_uri == EX + "Incident"
    ).schema_elements[0]
    assert node.backend == "another_graph_database"
    assert node.representation["binding"]["label"] == "Event"


def test_resource_loader_only_reads_content(
    monkeypatch,
):
    from io import BytesIO

    from graphrag.resource_loader import ResourceLoader

    class HttpFilesystem:
        def open(
            self,
            path,
            mode,
        ):
            assert path == "https://example.org/ontology.ttl" and mode == "rb"
            return BytesIO(b"content")

    loader = ResourceLoader()
    monkeypatch.setattr(
        loader, "_location", lambda uri: (HttpFilesystem(), str(uri), str(uri), "https")
    )
    resource = loader.read("https://example.org/ontology.ttl")
    assert resource.content == b"content"
    assert resource.source == "https://example.org/ontology.ttl"
    assert not hasattr(loader, "is_current")


def test_root_parser_override_does_not_override_import_format(resources):
    from rdflib import Graph

    ontology, _ = resources
    root = ontology.with_name("root.owl")
    graph = Graph().parse(
        data="""@prefix owl: <http://www.w3.org/2002/07/owl#> .
<https://example.org/root> a owl:Ontology ; owl:imports <https://example.org/import> .""",
        format="turtle",
    )
    root.write_text(graph.serialize(format="xml"))
    service = OntologyService(
        OntologySettings(
            path=root, format="xml", imports={"https://example.org/import": ontology}
        )
    )
    assert service.resolve("Incident").candidates[0].identifier == EX + "Incident"


def test_service_requires_explicit_abc_extensions():
    with pytest.raises(TypeError, match="extend OntologyProvider"):
        OntologyService(provider=object())
    with pytest.raises(TypeError, match="extend OntologyProvider"):
        OntologyService(provider=OntologyResources("ontology.ttl"))


def test_linkml_mapping_apis_preserve_reused_attribute_names(resources):
    _, schema = resources
    raw = yaml.safe_load(schema.read_text())
    raw["classes"]["Event"]["attributes"]["id"] = {
        "range": "integer",
        "slot_uri": "ex:eventIdentifier",
        "annotations": {"neo4j_property": "event_id"},
    }
    raw["classes"]["AttackType"]["attributes"] = {
        "id": {
            "range": "integer",
            "slot_uri": "ex:attackIdentifier",
            "annotations": {"neo4j_property": "category_id"},
        }
    }
    schema.write_text(yaml.safe_dump(raw))
    provider = load_linkml_mappings(schema)
    (event,) = mapped(provider, [EX + "eventIdentifier"])
    (attack,) = mapped(provider, [EX + "attackIdentifier"])
    assert event.schema_elements[0].schema_class == "Event"
    assert event.schema_elements[0].identifier == "event_id"
    assert attack.schema_elements[0].schema_class == "AttackType"
    assert attack.schema_elements[0].identifier == "category_id"
    assert tuple(
        provider.mappings[i]
        for i in provider.database_index[("Event", "event_id", None)]
    ) == (event,)


def test_linkml_native_mapping_kinds_and_proposal_metadata(resources):
    _, schema = resources
    raw = yaml.safe_load(schema.read_text())
    cls = raw["classes"]["Event"]
    cls.update(
        class_uri="ex:Incident",
        broad_mappings=["ex:BroadIncident"],
        narrow_mappings=["ex:NarrowIncident"],
        mappings=["ex:OtherMapping"],
    )
    cls["annotations"].update(
        mapping_status="proposed",
        mapping_provenance="Schema review",
        mapping_note="Needs review",
    )
    schema.write_text(yaml.safe_dump(raw))
    provider = load_linkml_mappings(schema)
    mappings = mapped(
        provider,
        [
            EX + "Incident",
            EX + "BroadIncident",
            EX + "NarrowIncident",
            EX + "OtherMapping",
        ],
    )
    assert {m.relation for m in mappings} == {
        "identity",
        "close",
        "broad",
        "narrow",
        "unspecified",
    }
    assert all(
        m.status == "proposed"
        and m.provenance == "Schema review"
        and m.note == "Needs review"
        for m in mappings
    )
    assert not mapped(provider, ["https://example.org/schema/Event"])


def test_multiple_schema_elements_can_map_to_one_concept(resources):
    _, schema = resources
    raw = yaml.safe_load(schema.read_text())
    raw["classes"]["Event"]["attributes"]["year"]["related_mappings"] = ["ex:Incident"]
    schema.write_text(yaml.safe_dump(raw))
    mappings = mapped(load_linkml_mappings(schema), [EX + "Incident"])
    assert {element.identifier for m in mappings for element in m.schema_elements} == {
        "Event",
        "year",
    }


def test_gtd_linkml_alone_contains_the_proposed_alignments():
    root = Path(__file__).resolve().parents[2]
    base = root / "project-resources/gtd"
    service = OntologyService(
        OntologySettings(
            path=base / "ontology/gtdonto.ttl",
            schema_path=base / "neo4j/schema.linkml.yaml",
        )
    )
    context = service.describe(["Incident"])
    assert any(
        m.ontology_uri.endswith("#Incident")
        and m.schema_elements[0].identifier == "Event"
        for m in context.mappings
    )
    assert all(m.status == "proposed" for m in context.mappings)
    assert len(context.schema_sources) == 1
    assert (
        service.resolve_database_element("Group", relationship_type="CARRIES_OUT")
        .mappings[0]
        .ontology_uri.endswith("#hasPerpGroup")
    )


@pytest.mark.parametrize(
    "query",
    [
        "SELECT ?unused WHERE {}",
        "SELECT ?value WHERE { VALUES ?value { UNDEF UNDEF UNDEF } }",
        "SELECT DISTINCT ?value WHERE { VALUES ?value { 1 1 2 3 } } ORDER BY ?value",
        "SELECT ?value WHERE { VALUES ?value { 1 2 3 4 } } ORDER BY ?value LIMIT 2 OFFSET 1",
        "SELECT (COUNT(?s) AS ?count) WHERE { ?s ?p ?o }",
        "SELECT ?s WHERE { { SELECT DISTINCT ?s WHERE { ?s ?p ?o } } } ORDER BY ?s",
        "SELECT ?s WHERE { ?s <http://www.w3.org/2000/01/rdf-schema#label> ?label } ORDER BY ?s",
    ],
)
def test_select_limit_preserves_native_query_semantics(
    resources,
    query,
):
    import json

    from rdflib import Graph

    ontology, _ = resources
    native = Graph().parse(ontology).query(query)
    expected = json.loads(native.serialize(format="json"))
    rows = expected["results"]["bindings"]
    expected["results"]["bindings"] = rows[:2]
    result = make_service(resources).query_sparql(query, limit=2)
    assert result.data == expected
    assert result.truncated == (len(rows) > 2)


def test_select_limit_stops_native_projection_after_lookahead(
    resources,
    monkeypatch,
):
    from rdflib.plugins.sparql import evaluate

    original = evaluate.evalProject
    produced = []

    def track_projection(
        context,
        projection,
    ):
        for binding in original(context, projection):
            produced.append(binding)
            yield binding

    monkeypatch.setattr(evaluate, "evalProject", track_projection)
    result = make_service(resources).query_sparql(
        "SELECT ?s WHERE { ?s ?p ?o }", limit=1
    )
    assert len(result.data["results"]["bindings"]) == 1
    assert result.truncated
    assert len(produced) == 2


def test_native_search_uses_lowercase_and_literal_query_text(
    resources,
):
    ontology, _ = resources
    with ontology.open("a") as stream:
        stream.write(
            'ex:Street rdfs:label "Straße" .\nex:Quoted rdfs:label "\\" } UNION { ?s ?p ?o } #" .\n'
        )
    service = make_service(resources)
    assert service.resolve("STRAẞE").candidates[0].identifier == EX + "Street"
    assert service.resolve("STRASSE").status == "not_found"
    assert service.search("STRAẞE", exact=True).entities[0].identifier == EX + "Street"
    assert (
        service.resolve('" } UNION { ?s ?p ?o } #').candidates[0].identifier
        == EX + "Quoted"
    )


def test_initialized_mapping_requests_do_not_parse_or_scan_resources(
    resources,
    monkeypatch,
):
    from graphrag.ontology import linkml_loader

    service = make_service(resources)
    service.initialize()
    data = service._mapping_data

    class IndexedOnly(tuple):
        def __iter__(self):
            pytest.fail("Requests must not scan the complete mapping collection")

    data.mappings = IndexedOnly(data.mappings)

    def unexpected_load(
        *args,
        **kwargs,
    ):
        pytest.fail("Requests must not parse schema resources after initialization")

    monkeypatch.setattr(linkml_loader, "load_linkml_mappings", unexpected_load)
    for resource in resources:
        resource.unlink()
    service.initialize()
    result = service.describe(["Incident"])
    assert any(m.schema_elements[0].identifier == "Event" for m in result.mappings)
    reverse = service.resolve_database_element("Event", property_name="year")
    assert reverse.mappings[0].ontology_uri == EX + "year"
    # Mutable nested response data must not modify the loaded associations.
    reverse.mappings[0].schema_elements[0].representation["binding"][
        "property"
    ] = "changed"
    assert (
        service.resolve_database_element("Event", property_name="year")
        .mappings[0]
        .schema_elements[0]
        .identifier
        == "year"
    )
    assert (
        service.resolve_database_element("Event", property_name="year")
        .mappings[0]
        .schema_elements[0]
        .representation["binding"]["property"]
        == "year"
    )


def test_mapping_indexes_preserve_collisions_and_all_alignments(
    resources,
):
    _ontology, schema = resources
    raw = yaml.safe_load(schema.read_text())
    raw["classes"]["AliasEvent"] = {
        "close_mappings": ["ex:Incident", "ex:Other"],
        "annotations": {"neo4j_label": "Event"},
    }
    schema.write_text(yaml.safe_dump(raw))
    service = make_service(resources)
    service.initialize()
    forward = service.describe(["Incident"])
    assert {
        m.schema_elements[0].schema_class
        for m in forward.mappings
        if m.ontology_uri == EX + "Incident"
    } == {"Event", "AliasEvent"}
    reverse = service.resolve_database_element("Event")
    assert {m.ontology_uri for m in reverse.mappings} == {EX + "Incident", EX + "Other"}
    assert len(reverse.mappings) == 3


def test_schema_mappings_are_optional_data_and_checked_at_startup(
    resources,
):
    ontology, schema = resources
    service = OntologyService(OntologySettings(path=ontology))
    service.initialize()
    assert not service.describe(["Incident"]).mappings
    with pytest.raises(TypeError, match="SchemaMappings data"):
        OntologyService(OntologySettings(path=ontology), schema_mappings=object())
    with pytest.raises(ValueError, match="unknown mapping"):
        SchemaMappings(database_index={("Event", None, None): (0,)})
    schema.write_text("invalid: [yaml")
    with pytest.raises(OntologyLoadError):
        make_service(resources).initialize()


def test_search_finds_all_configured_labels_not_just_display_label(resources):
    ontology, _ = resources
    with ontology.open("a") as stream:
        stream.write('ex:Incident rdfs:label "Événement"@fr .\n')
    service = make_service(resources)
    entity = service.search("événement", exact=True).entities[0]
    assert entity.identifier == EX + "Incident"
    assert entity.label == "Incident"
    assert service.resolve("ÉVÉNEMENT").status == "resolved"
