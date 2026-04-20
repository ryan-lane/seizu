![seizu logo](/images/logo-horizontal-black.svg#gh-light-mode-only)
![seizu logo](/images/logo-horizontal-white.svg#gh-dark-mode-only)

# Seizu (星図)

## What is Seizu?

[Seizu (星図)](https://mappedsky.github.io/seizu/) is a star chart for your security graph — a React + Python frontend for Neo4j data, built for [Cartography](https://github.com/cartography-cncf/cartography) and [Starbase](https://github.com/JupiterOne/starbase).

Seizu includes:

* A browser-editable dashboard with a row/panel layout and multiple panel types for visualizing Cypher query results
* An interactive Cypher query console with schema browsing and per-user history
* A built-in MCP server that exposes user-defined toolsets so LLM agents can query the graph alongside you
* A scheduled-query worker — runs Cypher on a schedule or on graph events, with action plugins (Slack, SQS, log)
* Native OIDC / JWT auth — connect Seizu directly to your IDP; no proxy required

## Getting started

Seizu has a [quickstart guide](https://mappedsky.github.io/seizu/dev/docker-compose.html#quickstart), which can be used for evaluation, or development.

## Documentation

* [Installation documentation](https://mappedsky.github.io/seizu/install/backend.html)
* [Dashboard configuration](https://mappedsky.github.io/seizu/install/dashboard.html)
* [Scheduled query documentation](https://mappedsky.github.io/seizu/install/scheduled-queries.html)
* [Basic development documentation](https://mappedsky.github.io/seizu/dev/docker-compose.html)
