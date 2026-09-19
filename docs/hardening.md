# Robustness and security hardening

Findings from a robustness and security review of the CrateDB MCP Server,
against MCP specification revisions `2025-11-25` and `2026-07-28`, and against
FastMCP 3.4 / 4.0.

Checked items are implemented on `main`, or on the branch noted inline.
Unchecked items are still open, with the rationale for deferring them kept
next to the item, so nobody has to guess why.

## P0, implemented

- [x] **CrateDB errors are no longer reported as successful tool results.**
  CrateDB returns an `error` object with an HTTP error status, which was
  passed through as a regular result, leaving the model with no error signal.
  Now translated into a tool execution error, per SEP-1303.
  Verified against CrateDB 6.5.0: `SELECT * FROM nope` reports
  `CrateDB error 4041: RelationUnknown[Relation 'nope' unknown]`.
- [x] **Non-JSON error responses no longer raise a bare `JSONDecodeError`.**
  Status code and a body excerpt are reported instead, e.g. for gateway error
  pages.
- [x] **Server internals are not forwarded to the model.** `error_trace` is
  stripped from responses, it may expose stack traces and file system paths.
- [x] **Tool annotations.** All tools announce `readOnlyHint`, `idempotentHint`,
  and `openWorldHint`, enabling client-side auto-approval and allowlisting.
- [x] **Result size limits.** `CRATEDB_MCP_RESULT_MAX_BYTES` (default 1 MB)
  guards SQL results, table metadata, and documentation pages. Oversized
  results are rejected with guidance to refine the query, instead of
  flooding the context window.
- [x] **Documentation downloads fail loudly.** `raise_for_status` was missing,
  error pages were returned as documentation content.
- [x] **HTTP transports require authentication, and validate `Host`/`Origin`.**
  `--auth-token` enables bearer authentication, the server refuses to bind a
  non-loopback address without it (`--allow-unauthenticated` is the explicit
  escape hatch), and `Host`/`Origin` validation is enabled by default.
  Verified: 401 without token, 403 on foreign `Origin`, 421 on foreign `Host`.
- [x] **Read-only statement filter widened, without weakening it.** `EXPLAIN`
  (for read-only statements), `SHOW`, and common table expressions are now
  permitted, previously they were rejected although documented as supported.
  Write statements hidden behind `EXPLAIN`, `EXPLAIN ANALYZE`, or a CTE, and
  multiple statements per request, stay rejected. Verified against CrateDB
  6.5.0, including `EXPLAIN ANALYZE`, which really executes the statement.
- [x] **Read-only enforcement is documented honestly.** The application-level
  filter is a convenience layer, the database user with `GRANT DQL` is the
  enforcement boundary.
- [x] **Secrets stay out of URLs.** Credentials are stripped from
  `CRATEDB_CLUSTER_URL` and applied as `Authorization` headers, so they cannot
  leak into logs, error messages, or traces. `CRATEDB_USERNAME`,
  `CRATEDB_PASSWORD`, and `CRATEDB_TOKEN` are supported.
- [x] **Documentation cache no longer writes into the working directory.**
  It uses the platform cache directory, and degrades to an uncached client
  when the location is not writable, e.g. on read-only file systems.
- [x] **Reverse proxy deployments can announce their hostnames.** `--allowed-host`
  and `--allowed-origin`, documented, because `Host` validation rejects
  unannounced hostnames with HTTP 421.
- [x] **Cluster connectivity is reported on startup**, so misconfiguration is
  visible in the client logs, without preventing startup, because the
  documentation tools work without a database connection.
- [x] **Regression tests for all of the above**, including hermetic tests
  through a mock HTTP transport, and protocol-level tests through an in-memory
  MCP client.
- [x] **Declared directly imported dependencies.** `httpx` and `platformdirs`
  were used, but only available transitively.
- [x] **Result size limits are enforced while receiving.** Responses are
  streamed and abandoned beyond the limit, so oversized results neither
  exhaust server memory, nor get serialized a second time for measuring.
- [x] **Users without a password can authenticate**, e.g. the default `crate`
  superuser, both through `CRATEDB_CLUSTER_URL` and `CRATEDB_USERNAME`.
- [x] **Statements which can not be analyzed are denied**, e.g. excessively
  nested ones, and chains of `EXPLAIN` keywords are classified in bounded time.
- [x] **Unexpected JSON payloads are reported as tool errors**, e.g. lists or
  strings returned by intermediaries.
- [x] **The documentation allowlist honors path boundaries**, so lookalike
  GitHub accounts like `crate-evil` are rejected.
- [x] **Each link of the documentation index can be fetched.** 13 of 100
  indexed links point outside the permitted URL prefixes, e.g. to
  `community.cratedb.com`, Read the Docs, and PostgreSQL driver documentation,
  so the server advertised resources it refused to deliver, and the model
  wasted a failing tool call on each of them. Indexed links are permitted by
  exact match now. That does not open any further prefix, and the index is
  curated within `cratedb-about`, which is the trust boundary already.
- [x] **Empty authentication tokens are rejected**, tokens are compared
  byte-wise, and a warning is emitted when credentials travel to a remote
  cluster over plain HTTP.
- [x] **Invalid cluster URLs are reported on startup** without echoing them,
  and the connectivity check uses a short timeout.
- [x] **Tool annotations reflect the permit-all mode.** With
  `CRATEDB_MCP_PERMIT_ALL_STATEMENTS`, `query_sql` is announced as destructive
  instead of read-only, so clients do not auto-approve writes.
- [x] **Statements are classified by their leading token.** sqlparse does not
  know each CrateDB statement, e.g. `OPTIMIZE` or `REFRESH`, which were
  classified by whatever keyword followed later.
- [x] **Denied statements are explained.** Reserved words used as identifiers,
  e.g. `SELECT update FROM t`, are denied, the error message now names the
  keyword and suggests quoting. `EXPLAIN` options are permitted.
- [x] **`get_table_columns` omits oversized sections** instead of failing
  altogether on large schemas, because the tool accepts no parameters the
  model could refine.
- [x] **The documentation cache may fail while serving requests**, e.g. when
  it is locked by another server process, the server carries on uncached.
- [x] **Container deployments can be secured through the environment**, using
  `CRATEDB_MCP_ALLOWED_HOSTS`, `CRATEDB_MCP_ALLOWED_ORIGINS`, and
  `CRATEDB_MCP_ALLOW_UNAUTHENTICATED`.
- [x] **Compatible dependency ranges.** `fastmcp>=3.4` is required for
  `Host`/`Origin` validation, and `hishel<0.2`, because v1 is not API-compatible.

Deferred from P0, deliberately:

- [ ] **Verify database-level read-only privileges on startup.** A reliable
  probe needs CrateDB privilege introspection, e.g. through
  `information_schema.applicable_roles`, which has to be validated against
  supported CrateDB versions first. Until then, the startup check reports
  connectivity only. Add when the introspection semantics are verified.
- [ ] **`ResponseLimitingMiddleware` instead of explicit size guards.** Truncating
  a response breaks tools that announce an output schema, verified with
  FastMCP 3.4.7. Revisit together with the typed tool outputs below.

## P1, next

- [ ] **OAuth / JWT authentication for multi-user and hosted deployments.** The
  bearer token is a single shared secret, without per-user identity, expiry,
  or audit trail, and clients supporting OAuth only can not use it. FastMCP
  provides JWT verification and OAuth providers, and `CrateDbMcp(auth=...)`
  accepts any token verifier already, so the CLI needs options to configure
  one. Identity from the verified token is also the prerequisite for auditing
  who ran which statement.
- [x] **Shared `httpx.Client`** with connection pooling.
- [ ] **Retries for idempotent requests** to CrateDB.
- [ ] **Follow redirects for documentation resources**, validating each hop
  against the allowlist. Currently, redirects are reported as errors.
- [ ] **Migrate to the `hishel` v1 API.**
- [ ] **Typed tool results.** `query_sql` announces a free-form object as its
  output schema, so clients cannot rely on structured content.
- [ ] **Tool timeouts and background tasks.** Long-running analytics queries can
  block the stdio loop. FastMCP supports `timeout=` and SEP-1686 tasks.
- [ ] **Expose documentation as MCP resources, and the system prompt as an MCP
  prompt.** Currently zero resources and zero prompts are registered, although
  the protocol separates data from actions for exactly this reason.
- [ ] **Observability.** Structured logging, per-request correlation IDs,
  `TimingMiddleware`, and a readiness endpoint for the HTTP transport.
- [ ] **Do not log query text at `INFO`.** SQL may contain personal data, the
  SQL filter currently logs the leading 50 characters of permitted and denied
  expressions.
- [ ] **Abuse control for shared deployments.** Rate limiting and concurrency
  caps, so a single agent cannot overload a shared cluster.
- [ ] **Disable FastMCP outbound traffic.** The framework checks PyPI for
  updates on startup, which is undesirable for air-gapped deployments. Note:
  the setting is `FASTMCP_CHECK_FOR_UPDATES=off`, a `false` value aborts
  startup with a pydantic validation error.
- [x] **Moved the cache of the documentation index off import time**, its
  lifetime is read at runtime now. `cachetools` is no longer needed.

## P2, strategic

- [ ] **Migrate to FastMCP 4 and the `2026-07-28` protocol revision.** The
  stateless revision removes the handshake and sessions, adds multi-round-trip
  requests, and lets any replica behind an ordinary load balancer answer a
  request. FastMCP 4 serves both protocol eras from one deployment, so the
  migration is a version bump plus an audit, not a rewrite.
- [ ] **Harden the OCI images.** They run as `root`, and the `mcpo` image binds
  `0.0.0.0` without an API key.
- [ ] **Supply chain.** Pin GitHub Actions to commit SHAs, add `pip-audit` to CI,
  and publish SBOMs for the OCI images. The number of FastMCP releases driven
  by vulnerabilities justifies automating the detection.
- [ ] **`python -m cratedb_mcp` is a silent no-op.** `cratedb_mcp/__main__.py`
  never invokes the CLI, the process exits immediately with status zero.
- [ ] **Publish to the MCP registry** (`server.json`), and add icons (SEP-973).
- [ ] **Re-enable MyPy in CI**, it is currently disabled.
- [ ] **Refactorings from `docs/backlog.md`:** extract the SQL filter into
  `cratedb-sqlparse`, and support declarative `fastmcp.json` configuration.
