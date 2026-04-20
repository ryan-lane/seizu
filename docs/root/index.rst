Seizu (星図)
============

What is Seizu?
--------------

`Seizu (星図) <https://mappedsky.github.io/seizu/>`_ is a react/mui frontend and python backend for various forms of reporting of Neo4j graph data.
It is well suited for building reporting for tools like `cartography <https://github.com/lyft/cartography>`_ and `starbase <https://github.com/JupiterOne/starbase>`_

Seizu includes:

* A configuration-driven react/mui frontend, with support for a dashboard, arbitrary reports, using a row/panel based layout with various panel types for visualizing data
* An interactive **Query Console** for running ad-hoc Cypher queries, with graph, table, and raw result views, and a collapsible database schema browser showing available node labels, relationship types, and property keys
* A backend worker that can run queries on a schedule, or triggered by graph events, with action plugins that can use the results; for example, sending query results to a slack channel, or an sqs queue
* A backend worker that can push query results from panels into statsd, for historical data tracking purposes
* An **MCP server** at ``/api/v1/mcp`` that exposes user-defined Cypher-backed tools to LLM agents such as Claude
* A mechanism of providing SSO for Neo4j, when Seizu is placed behind an OAuth2 proxy

Getting started
---------------

Seizu has a `quickstart guide <https://mappedsky.github.io/seizu/install/quickstart.html>`_, which can be used for evaluation, or development.

Documentation
-------------

* `Installation documentation <https://mappedsky.github.io/seizu/install/backend.html>`_
* `Dashboard configuration <https://mappedsky.github.io/seizu/install/dashboard.html>`_
* `Query Console <https://mappedsky.github.io/seizu/install/query-console.html>`_
* `Scheduled query documentation <https://mappedsky.github.io/seizu/install/scheduled-queries.html>`_
* `MCP Toolsets documentation <https://mappedsky.github.io/seizu/install/mcp-toolsets.html>`_
* `Basic development documentation <https://mappedsky.github.io/seizu/dev/dependencies.html>`_

.. toctree::
    :caption: Installation & Configuration
    :hidden:

    install/quickstart
    install/backend
    install/dashboard
    install/query-console
    install/scheduled-queries
    install/mcp-toolsets
    install/stats

.. toctree::
    :caption: Development
    :hidden:

    dev/dependencies
    dev/test
    dev/contributing

.. toctree::
    :caption: Get In Touch
    :hidden:

    contact/security
    contact/code-of-conduct
