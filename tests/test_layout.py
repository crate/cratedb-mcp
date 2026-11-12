import os

import pytest

from cratedb_mcp import tool
from cratedb_mcp.tool import (
    GB,
    SYSTEM_SCHEMAS,
    analyze_table_layout,
    query_cratedb,
    score_cluster,
    score_layout,
)

SCHEMA = "testdrive_layout"


@pytest.fixture(scope="module", autouse=True)
def tables():
    query_cratedb("DROP TABLE IF EXISTS testdrive_layout.readings")
    query_cratedb("DROP TABLE IF EXISTS testdrive_layout.devices")
    query_cratedb(
        "CREATE TABLE testdrive_layout.readings (id INT, day TIMESTAMP) "
        "CLUSTERED INTO 2 SHARDS PARTITIONED BY (day) WITH (number_of_replicas = 0)"
    )
    query_cratedb(
        "CREATE TABLE testdrive_layout.devices (id INT) "
        "CLUSTERED INTO 1 SHARDS WITH (number_of_replicas = 1)"
    )
    query_cratedb("INSERT INTO testdrive_layout.readings VALUES (1, 0), (2, 86400000), (3, 0)")
    query_cratedb("INSERT INTO testdrive_layout.devices VALUES (1), (2)")
    query_cratedb("REFRESH TABLE testdrive_layout.readings, testdrive_layout.devices")
    yield
    query_cratedb("DROP TABLE IF EXISTS testdrive_layout.readings")
    query_cratedb("DROP TABLE IF EXISTS testdrive_layout.devices")


@pytest.mark.parametrize(
    "layout",
    [(1, 0, 200_000_000, 200_000_000, 1_000_000), (8, 0, 200_000_000, 300_000_000, 1_000_000)],
    ids=["one-small-shard", "small-shards-within-cpus"],
)
def test_score_layout_quiet_for_small_tables(layout):
    assert score_layout(*layout, cpus=8) == []


@pytest.mark.parametrize(
    "layout, finding",
    [
        ((6, 0, 40 * GB, 73 * GB, 1_000_000), "The largest shard holds 73.0 GB"),
        ((6, 0, 20 * GB, 30 * GB, 250_000_000), "holds 250,000,000 records"),
        ((730, 365, 12_000_000, 20_000_000, 1_000), "The table has 730 shards with 12.0 MB"),
    ],
    ids=["shard-above-50-gb", "shard-above-200-million-records", "small-shards-above-cpus"],
)
def test_score_layout_names_problem_and_number(layout, finding):
    findings = score_layout(*layout, cpus=16)
    assert len(findings) == 1
    assert finding in findings[0]


@pytest.mark.parametrize(
    "partitions, advice",
    [(0, "Use fewer shards."), (365, "Use fewer shards per partition, or fewer partitions.")],
)
def test_score_layout_fits_shard_advice_to_partitioning(partitions, advice):
    (finding,) = score_layout(730, partitions, 12_000_000, 20_000_000, 1_000, cpus=16)
    assert finding.endswith(f"starting point. {advice}")


def test_score_cluster_warns_at_90_percent_of_shard_limit():
    assert score_cluster(899, 1000) == []
    assert "The busiest node holds 900 shards" in score_cluster(900, 1000)[0]


def test_analyze_table_layout_counts_shards_and_partitions():
    report = analyze_table_layout(SCHEMA)
    tables = {table.name: table for table in report.tables}
    assert set(tables) == {"readings", "devices"}

    readings = tables["readings"]
    assert readings.partitions == 2
    assert readings.primary_shards == 4
    assert readings.replica_shards == 0
    assert readings.records == 3
    assert readings.max_shard_records <= 2

    devices = tables["devices"]
    assert devices.partitions == 0
    assert devices.primary_shards == 1
    assert devices.replica_shards == 1
    assert devices.unassigned_shards == 1
    assert devices.records == 2
    assert devices.avg_shard_bytes == devices.max_shard_bytes > 0
    assert devices.findings == []

    assert report.max_shards_per_node > 0
    assert report.busiest_node_shards > 0
    assert report.cpus >= 1


def test_analyze_table_layout_finds_table_by_name_in_any_schema():
    report = analyze_table_layout(table="devices")
    assert {table.name for table in report.tables} == {"devices"}
    assert SCHEMA in {table.schema_name for table in report.tables}


def test_analyze_table_layout_leaves_out_system_schemas_and_ranks_tables():
    report = analyze_table_layout(max_tables=1000)
    assert {(SCHEMA, "readings"), (SCHEMA, "devices")} <= {
        (table.schema_name, table.name) for table in report.tables
    }
    assert not {table.schema_name for table in report.tables} & set(SYSTEM_SCHEMAS)
    keys = [(not table.findings, -(table.size_bytes or 0)) for table in report.tables]
    assert keys == sorted(keys)


def test_analyze_table_layout_caps_tables():
    report = analyze_table_layout(max_tables=1)
    assert len(report.tables) == 1
    assert report.truncated is True
    assert "Only 1 of" in report.note


def test_analyze_table_layout_says_when_the_first_table_alone_passes_the_character_cap(mocker):
    mocker.patch.dict(os.environ, {"CRATEDB_MCP_MAX_CHARS": "10"})
    report = analyze_table_layout(schema=SCHEMA)
    assert report.tables == []
    assert report.truncated is True
    assert "No tables are shown, because the first table alone holds " in report.note
    assert "characters, more than the cap of 10." in report.note


def test_analyze_table_layout_without_access_to_sys_tables(mocker):
    real_query = tool.query_cratedb

    def refuse_sys(query, args=None):
        if "sys." in query:
            return {"error": {"message": "SchemaUnknownException[Schema 'sys' unknown]"}}
        return real_query(query, args)

    mocker.patch.object(tool, "query_cratedb", side_effect=refuse_sys)
    report = analyze_table_layout(SCHEMA, "readings")
    readings = report.tables[0]
    assert readings.partitions == 2
    assert readings.number_of_shards == 2
    assert readings.primary_shards is None
    assert readings.findings == []
    assert report.truncated is False
    assert "Shard counts, sizes and findings are missing" in report.note
    assert "Schema 'sys' unknown" in report.note
