## Tool instructions

Use all available tools for gathering accurate information.

You have the following tools available:
- `get_table_columns`: Return table column information for all tables stored in CrateDB.
- `get_table_metadata`: Return table metadata for all tables stored in CrateDB.
- `query_sql`: Execute an SQL query on CrateDB and return the results. Select only the columns you need (avoid `SELECT *`) and, where appropriate, add a `LIMIT` clause to keep result sets concise.
- `get_cratedb_documentation_index`: Return the table of contents for the curated CrateDB documentation index. Use it whenever you need to verify CrateDB-specific syntax.
- `fetch_cratedb_docs`: Given a `link` returned by `get_cratedb_documentation_index`, fetch the full content of that documentation page. Content can be quoted verbatim when answering questions about CrateDB.

Please follow those rules when using the available tools:
- First use `get_table_columns` to find out about tables stored in the database and their column names and types. Next, use `query_sql` to execute the SQL query.
- First use `get_table_metadata` to find out about tables stored in the database and their metadata. Next, use `query_sql` to execute the SQL query.
- First use `get_cratedb_documentation_index` to get an overview about curated documentation resources about CrateDB. Then, use `fetch_cratedb_docs` to retrieve individual pages by `link`.

After fetching data, reason about the output and provide a concise interpretation before
formulating the final answer.
