# Development documentation

## Sandbox

Use those commands to set up a development sandbox and install the
project in editable mode.
```shell
git clone https://github.com/crate/cratedb-mcp
cd cratedb-mcp
uv venv --python 3.13 --seed .venv
source .venv/bin/activate
uv pip install --upgrade --editable='.[develop,test]'
```

## Software tests

Fist, you will need to prepare the httpbin service:

```shell
docker pull kennethreitz/httpbin
docker run -p 8008:80 kennethreitz/httpbin
export GO_HTTPBIN_URL=http://localhost:8008
```

Moreover, you will need to start a CrateDB server:

```shell
docker run --rm   --publish=4200:4200 --publish=5432:5432 --env=CRATE_HEAP_SIZE=2g   crate:latest -Cdiscovery.type=single-node
```

The project uses the [poethepoet] task runner, which provides convenience entry
points for invoking linters and software tests. The top-level one-shot command
will invoke both and is also used on CI/GHA.
```shell
poe check
```

To invoke individual software tests for working on the spot, use a
traditional `pytest` invocation. Examples:
```shell
pytest --no-cov tests/test_knowledge.py
```
```shell
pytest --no-cov -k query
```

## Release

The project uses [versioningit] so you don't need to do any version bumping
within files because the version number will be derived from the Git tag.

However, you need to designate the new release within the [CHANGES.md](./changes.md)
file, and commit it. The release procedure currently looks like this:
```shell
git commit -m 'Release v0.0.1'
git tag v0.0.1
git push && git push --tags
```


[poethepoet]: https://pypi.org/project/poethepoet/
[versioningit]: https://pypi.org/project/versioningit/
