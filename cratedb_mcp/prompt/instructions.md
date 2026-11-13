## Tool instructions

Find the data step by step before writing SQL: use `list_schemas` to see where
tables live, `list_tables` to see the tables and views of one schema, and
`describe_table` to read the columns of the tables you need. Then use `query_sql`.

To verify CrateDB-specific details or syntax, use `get_cratedb_documentation_index`,
then `fetch_cratedb_docs` to retrieve the pages you need by `link`.

After fetching data, reason about the output and provide a concise interpretation before
formulating the final answer.
