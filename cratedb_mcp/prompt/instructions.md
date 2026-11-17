This server gives access to one CrateDB cluster and to the CrateDB documentation.

CrateDB speaks the PostgreSQL wire protocol and much of its SQL, but it is a different
database: a PostgreSQL function, operator or type may be missing or behave differently.
When a statement fails, read the error and look the feature up with
`get_cratedb_documentation_index` and `fetch_cratedb_docs` before you try variants.

These differences give a wrong or slow answer without an error:
- Filter a time range on the bare column: `ts >= '2025-07-01' AND ts < '2025-08-01'`.
  A function around the column, such as `DATE_TRUNC('day', ts)`, scans every row and
  every partition.
- Subtract time with an interval: `now() - INTERVAL '7 days'`. `CURRENT_DATE - 7`
  returns an interval, not a date.
- Arrays start at 1, and `tags[0]` is NULL.
- On a column with a FULLTEXT index, `=` compares single words: `body = 'hello'` matches
  'hello world', and `body = 'hello world'` matches nothing. Search such a column with
  `MATCH(body, 'hello')`.
- A pattern for `~` must match the whole value: `note ~ 'disk'` finds nothing in
  'disk full'. Write `note ~ '.*disk.*'`.

These forms replace PostgreSQL ones that fail:
- Latest value: `MAX_BY(value, ts)`, also with GROUP BY. `DISTINCT ON` and `LATERAL` do
  not exist.
- Object field: `obj['field']`, not `->>` or `obj.field`.
- Distinct count on a large table: `hyperloglog_distinct(col)`. `count(DISTINCT col)`
  can exceed the memory limit.
- Percentile: `percentile(value, 0.95)`.
- A column name with upper-case letters needs double quotes.
