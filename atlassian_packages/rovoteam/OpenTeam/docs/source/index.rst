================================
Responsible AI API Documentation
================================

The Responsible AI API is the HTTP service that owns content moderation
for Atlassian product surfaces. It exposes four endpoint families —
text moderation, image moderation, admin (feature-flag and
configuration) controls, and health/observability endpoints — over a
Flask + FlaskMicros stack, and routes incoming requests through a
small set of principal modules: the ``controllers`` blueprint tree,
the per-kind ``service`` orchestrators, the ``inference_models``
clients (Triton, AI Gateway, SageMaker), and the cross-cutting
``config``, ``feature_service``, ``slauth``, and ``metrics`` modules.

This documentation is written to be read end-to-end at least once.
Each page anchors back to the file paths and (where useful) line
numbers it documents, so a reader can verify claims against the
source. After the first read, individual pages serve as reference
material for runbooks, configuration audits, and onboarding new
contributors.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   introduction
   getting-started
   architecture
   service-layer
   inference-models
   configuration
   api-reference
   operations
   glossary

Indices and tables
==================

* :ref:`genindex`
* :ref:`search`
