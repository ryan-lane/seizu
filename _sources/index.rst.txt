.. image:: images/logo-horizontal-with-text-black.png
    :alt: seizu logo

Seizu (星図)
============

What is Seizu?
--------------

`Seizu (星図) <https://paypay.github.io/seizu/>`_ is a react/mui frontend and python backend for various forms of reporting of Neo4j graph data.
It is well suited for building reporting for tools like `cartography <https://github.com/lyft/cartography>`_ and `starbase <https://github.com/JupiterOne/starbase>`_

Seizu includes:

* A configuration-driven react/mui frontend, with support for a dashboard, arbitrary reports, using a row/panel based layout with various panel types for visualizing data
* A backend worker that can run queries on a schedule, or triggered by graph events, with action plugins that can use the results; for example, sending query results to a slack channel, or an sqs queue
* A backend worker that can push query results from panels into statsd, for historical data tracking purposes
* A mechanism of providing SSO for Neo4j, when Seizu is placed behind an OAuth2 proxy

Getting started
---------------

Seizu has a `quickstart guide <https://paypay.github.io/seizu/dev/docker-compose.html#quickstart>`_, which can be used for evaluation, or development.

Documentation
-------------

* `Installation documentation <https://paypay.github.io/seizu/install/backend.html>`_
* `Dashboard configuration <https://paypay.github.io/seizu/install/dashboard.html>`_
* `Scheduled query documentation <https://paypay.github.io/seizu/install/scheduled-queries.html>`_
* `Basic development documentation <https://paypay.github.io/seizu/dev/docker-compose.html>`_

.. toctree::
    :caption: Installation & Configuration
    :hidden:

    install/backend
    install/dashboard
    install/schema
    install/scheduled-queries
    install/stats

.. toctree::
    :caption: Development
    :hidden:

    dev/docker-compose
    dev/dependencies
    dev/test
    dev/contributing

.. toctree::
    :caption: Get In Touch
    :hidden:

    contact/security
    contact/code-of-conduct
