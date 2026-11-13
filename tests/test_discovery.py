import asyncio

import pytest
from fastmcp import Client

from cratedb_mcp import tool
from cratedb_mcp.core import CrateDbMcp
from cratedb_mcp.tool import describe_table, list_schemas, list_tables, query_cratedb

SCHEMA = "testdrive_discovery"


@pytest.fixture(scope="module", autouse=True)
def sensors():
    query_cratedb("DROP VIEW IF EXISTS testdrive_discovery.sensors_view")
    query_cratedb("DROP TABLE IF EXISTS testdrive_discovery.sensors")
    query_cratedb(
        "CREATE TABLE testdrive_discovery.sensors (id INT, day TIMESTAMP, value DOUBLE) "
        "CLUSTERED INTO 2 SHARDS PARTITIONED BY (day)"
    )
    query_cratedb("INSERT INTO testdrive_discovery.sensors VALUES (1, 0, 1.5), (2, 86400000, 2.5)")
    query_cratedb("REFRESH TABLE testdrive_discovery.sensors")
    query_cratedb(
        "CREATE VIEW testdrive_discovery.sensors_view AS "
        "SELECT id, value FROM testdrive_discovery.sensors"
    )
    yield
    query_cratedb("DROP VIEW IF EXISTS testdrive_discovery.sensors_view")
    query_cratedb("DROP TABLE IF EXISTS testdrive_discovery.sensors")


def test_list_schemas_counts_tables_and_views():
    schemas = {schema.schema_name: schema for schema in list_schemas()}
    assert schemas[SCHEMA].tables == 1
    assert schemas[SCHEMA].views == 1
    assert "sys" not in schemas
    assert "information_schema" not in schemas


def test_list_schemas_includes_system_schemas_on_request():
    names = [schema.schema_name for schema in list_schemas(include_system=True)]
    assert "sys" in names
    assert "information_schema" in names


def test_list_tables_names_kinds():
    tables = [(table.name, table.kind) for table in list_tables(SCHEMA)]
    assert tables == [("sensors", "table"), ("sensors_view", "view")]


def test_list_tables_filters_by_pattern():
    assert [table.name for table in list_tables(SCHEMA, pattern="%view")] == ["sensors_view"]


def test_list_tables_answers_an_unknown_schema_with_an_empty_list_as_text():
    async def call():
        async with Client(CrateDbMcp().mcp) as client:
            return await client.call_tool("list_tables", {"schema": f"{SCHEMA}_unknown"})

    result = asyncio.run(call())
    assert [block.text for block in result.content] == ["[]"]
    assert result.structured_content == {"result": []}


def test_describe_table_returns_definition_and_storage():
    description = describe_table(SCHEMA, "sensors")
    assert description.kind == "table"
    assert '"value" DOUBLE PRECISION' in description.definition
    assert 'PARTITIONED BY ("day")' in description.definition
    assert description.records == 2
    assert description.partitions == 2
    assert description.primary_shards == 4


def test_describe_view_returns_its_query():
    description = describe_table(SCHEMA, "sensors_view")
    assert description.kind == "view"
    assert "sensors" in description.definition
    assert description.records is None


def test_describe_system_table_returns_columns():
    description = describe_table("sys", "nodes")
    assert "hostname text" in description.definition.splitlines()


def test_describe_unknown_table_fails():
    with pytest.raises(ValueError) as ex:
        describe_table(SCHEMA, 'sensors"; DROP TABLE sensors; --')
    assert ex.match("Table or view not found")


def test_describe_table_without_access_to_sys_shards(mocker):
    real_query = tool.query_cratedb

    def refuse_sys(query, args=None):
        if "sys.shards" in query:
            return {"error": {"message": "SchemaUnknownException[Schema 'sys' unknown]"}}
        return real_query(query, args)

    mocker.patch.object(tool, "query_cratedb", side_effect=refuse_sys)
    description = describe_table(SCHEMA, "sensors")
    assert 'PARTITIONED BY ("day")' in description.definition
    assert description.records is None
