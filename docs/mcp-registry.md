# Official MCP Registry distribution

Docket Lens is published as `com.blackswancausallabs/regintel-mcp`.
The display name is **Docket Lens**. This listing distributes the retrieval server,
not a hosted analysis endpoint or the separately licensed Explorer.

## Install the MCP bundle

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first and
ensure your MCP application's environment can find `uv` on PATH. The bundle uses
`uv run` to install the declared Python dependencies and start the stdio server.
An internet connection is required on first launch. Python 3.11 or later is required;
uv can provision a compatible interpreter if needed.

Download the `.mcpb` asset from the matching GitHub release and import it in an
MCP client supporting source bundles with a Python server and custom launch command.
Supply your own Regulations.gov API key and select a writable working directory.
The key is supplied through the environment; no key, cache, corpus or local analysis
is included in the bundle. Client bundle support varies; the README's source checkout
installation remains available for other clients.

The bundled commands and skills describe the wider analysis workflow and its
human checkpoints. Connecting the retrieval server alone does not perform that
analysis or generate an Explorer.

## Release

1. Update versions in `pyproject.toml`, `manifest.json` and `server.json`.
2. Run tests and `python scripts/build_mcpb.py`.
3. Upload the bundle to the matching GitHub release, and set `fileSha256` in
   `server.json` to the bundle's SHA-256 hash.
4. Authenticate with `mcp-publisher login dns --domain blackswancausallabs.com` using the existing domain signing key, then run `mcp-publisher publish`. Keep private key material out of source control and logs.

The **MCP Registry maintenance** workflow validates metadata. Domain publication requires DNS authentication, not GitHub OIDC. `server.json` is the checked-in Registry record.

The earlier `io.github.Black-Swan-Causal-Labs/regintel-mcp` listing is retired in favor of the domain namespace used by the other Black Swan Causal Labs servers.
