.. _infra-overview:

==============================
Infrastructure and Operations
==============================

.. note::

   This page documents the deployment surface, runtime configuration,
   quality gates, and operational runbooks for the moderation
   service. It is a single combined page because the deployment
   artifacts (``Dockerfile``, ``helm/``, ``nebulae.yml`` …) and the
   operational runbooks they enable are read against the *same* set
   of source files; splitting them makes cross-reference noisy.

   For the local-vs-deployed run modes and developer bootstrap, see
   :ref:`getting-started`. For the wiring diagram and how the
   ``app_context`` object hangs the dependency graph together, see
   :ref:`architecture`. For the environment variables and feature
   flags consulted at startup, see :ref:`config-overview`. For the
   model-side failure modes that the runbooks address, see
   :ref:`inf-models`.

   Two anchors live on this page:

   * ``_infra-overview:`` — the top of the page, covering the
     deployment surface, runtime config, and quality gates.
   * ``_ops-overview:`` — partway down, covering the runbooks and
     monitoring & alerting hooks.

   External links to the operational portion should target
   ``_ops-overview:`` directly to avoid landing readers on the
   build-system material.

.. contents::
   :local:
   :depth: 2

Purpose & scope
===============

The moderation service is deployed under Atlassian's Micros
convention: a Docker image built from a project-root ``Dockerfile``,
declared to the Micros control plane via ``nebulae.yml`` plus a
matching set of descriptor files, and rolled out by Spinnaker
pipelines whose stages and triggers are pinned by an
*archetype*-tracked YAML. The runtime is a gunicorn + gevent
process; gevent monkey-patching and ``grpc.experimental.gevent``
initialization happen before any application import. The quality
gates that fence merges to ``master`` are local
(pre-commit, ``.githooks/pre-commit``) and remote (Bitbucket
Pipelines + Sonar + Sauron + pyright + per-module coverage floors).

This page answers four questions:

#. **What gets shipped?** — the deployment surface and the artifacts
   that describe it (`Deployment surface`_).
#. **How does the running process come up?** — the gunicorn entry
   point, the gevent / gRPC patching order, and the logging plumbing
   (`Runtime`_).
#. **What stops a bad change from getting in?** — pre-commit, type
   checks, coverage floors, Sonar / Sauron rules
   (`Quality gates`_).
#. **What does on-call do when something breaks?** — the three
   runbooks under `Operational runbooks`_.

What this page is **not**:

* It is **not** a deployment how-to. There is no "click these
  buttons in Spinnaker" section. The pipelines are auto-triggered;
  manual interventions are documented per-runbook.
* It is **not** a Helm-chart reference. Where a chart value is
  load-bearing for an operational decision (replica count, resource
  requests, readiness probe), the value is named here and
  referenced; the rest is left to the chart's own ``values.yaml``.
* It is **not** an authoritative on-call directory. Where an
  ownership / rotation / dashboard URL is *not* derivable from the
  source tree, that gap is flagged in `Operational ambiguities`_.

Deployment surface
==================

The deployment surface is the set of files in the repository root
that the Atlassian Micros tooling, Spinnaker, and Bitbucket
Pipelines consume. They are listed below in roughly the order they
are read during a release: build → describe → deploy → verify.

Atlassian Micros conventions
----------------------------

Atlassian Micros expects three coordinated descriptors at the
project root. They differ in *who* reads them and *when*:

.. list-table:: Micros descriptors at a glance
   :header-rows: 1
   :widths: 30 25 45

   * - File
     - Read by
     - Purpose
   * - ``nebulae.yml``
     - Nebulae control plane (per environment)
     - The runtime contract: image reference, environment variables,
       resource requests / limits, scaling policy, ingress/egress
       configuration, secrets bindings. This is what changes between
       ``ddev`` (developer dev), ``stg``, and ``prod`` deployments.
   * - ``project-descriptor.yml``
     - Micros project registry
     - Identifies the service to Micros: project key, owning team,
       service tier, support contacts. Typically changes once at
       service creation.
   * - ``archetype-descriptor.yaml``
     - Micros archetype tooling
     - Pins the *archetype version* this service tracks. The
       archetype is a centrally curated bundle of Spinnaker stages,
       canary configuration, and rollout policy. Bumping the
       archetype is how the platform team pushes deployment-pipeline
       changes uniformly across services.
   * - ``alias-descriptor.yml``
     - Micros DNS / aliasing
     - Maps the deployed service to its public DNS aliases (per
       environment). Reading the aliases is how a runbook author
       discovers the canonical URL for a given environment.
   * - ``env_nebulae.json``
     - Build / release tooling
     - Environment-name → Nebulae profile mapping consumed at
       release time so the tooling knows which ``nebulae.yml`` block
       applies to which target. Treat as read-only; it is generated
       from the archetype.

These five files are coupled: a ``nebulae.yml`` change that
introduces a new environment variable also needs the corresponding
secret bound (in ``nebulae.yml``) and — if the variable changes
runtime behaviour at startup — a ``getting-started`` /
``config-overview`` doc update. The ``archetype-descriptor.yaml``
should not be edited by hand outside of an archetype bump; the
archetype tooling will overwrite it.

``nebulae-plugins/`` extends the base Micros runtime with project-
specific plugins (e.g. extra side-cars, extra observability hooks,
or extra readiness checks) — anything declared here is loaded by
the Micros agent on the running container *in addition* to what
``nebulae.yml`` configures. Plugins here are load-bearing: a
removed plugin may silently disable a side-car the runbooks below
assume is running. Treat ``nebulae-plugins/`` as part of the change
review surface.

Container build
---------------

* ``Dockerfile`` — single-stage or multi-stage build that produces
  the runtime image. Three things are load-bearing for operations:

  #. **Working directory.** The image's ``WORKDIR`` must be the
     project root. The tokenizer factories in ``inference_models``
     load tokenizers via *relative paths* like
     ``"tokenizers/rai_ft_v2_2"`` — see :ref:`inf-models` for the
     working-directory dependency. A ``WORKDIR`` regression silently
     fails at startup as a tokenizer load error.
  #. **Entry point shape.** Production starts gunicorn, *not*
     ``flask run``. The ``flask run`` path is a developer
     convenience only (see ``.flaskenv`` below) and is not part of
     the deployed contract.
  #. **gevent + gRPC at import time.** ``src/gunicorn.conf.py`` (the
     gunicorn config module the entry point loads) does the
     monkey-patch *before* any other application import. The image
     must keep that ordering — moving any application import
     earlier in the boot path is a footgun (see `Runtime`_).

* ``.dockerignore`` — keeps the image small and reproducible by
  excluding the ``.git`` directory, local virtualenvs, IDE state,
  ``__pycache__``, test fixtures and the ``docs/`` tree. A bloated
  image is not just a build-time concern: it slows pull on every
  rolling-update and stretches the readiness window during
  Spinnaker bake stages.

Helm charts
-----------

``helm/`` holds the chart used by the Micros runtime to render the
Kubernetes manifests for the service. Inspect ``helm/values.yaml``
(and the matching environment-specific overlays, conventionally
``values-<env>.yaml``) when a runbook calls for it. The values that
are most often consulted from a runbook:

* **Replica count.** The horizontal-scale knob. The HTTP pool
  exhaustion runbook (`Runbook: HTTP pool exhaustion`_) considers a
  replica scale-up as the second-line mitigation after identifying
  the slow downstream.
* **Resource requests / limits.** CPU and memory floors / ceilings.
  A gunicorn process pinned to an under-provisioned CPU request
  will surface as *latency*, not as an OOM.
* **Readiness / liveness probes.** The readiness probe is what
  Spinnaker watches during the canary stage; if the gunicorn
  process is up but the model layer's tokenizers failed to load,
  the readiness probe should fail (see :ref:`inf-models`,
  Loading-at-startup section).

The chart itself is not a runbook. Treat it as a *binding* between
the platform contract (``nebulae.yml``) and the Kubernetes API.

Spinnaker pipelines
-------------------

Two YAMLs together define the deployment pipelines:

* ``default-pipelines.spinnaker.yaml`` — the **service-owned**
  copy. This is the pipeline definition Spinnaker syncs; edit here
  to add a stage that is specific to this service (e.g. a custom
  smoke test).
* ``default-pipelines.spinnaker-archetype.yaml`` — the **archetype-
  tracked** copy. This is what the Micros archetype tooling
  re-applies on bumps. Diffs between the two are how the platform
  team detects drift; in steady state they are kept in sync.

What's load-bearing for operations *without* re-pasting the YAML:

* **Canary stage.** The pipeline runs a Kayenta-style automated
  canary analysis between the new build and the running baseline
  before promoting to full traffic. The canary failing is the most
  common reason a deploy is *blocked*, not crashed.
* **Rollback trigger.** A failed canary or a failing readiness
  probe past the bake threshold triggers an automatic rollback to
  the previous image — no operator action required. Manual
  rollback is exposed as a Spinnaker *Rollback* stage on the
  pipeline; it re-deploys the prior good image and (because the
  service is stateless) does not require a data restore step.
* **Multi-environment progression.** ``ddev`` → ``stg`` → ``prod``
  in sequence; each promotion gate is a successful canary +
  manual judgement (or auto-promote, depending on archetype
  configuration).

When a runbook says "watch the deploy pipeline," the canary stage
is the one whose metrics matter (see `Monitoring & alerting hooks`_).

CI / build
----------

* ``bitbucket-pipelines.yml`` — CI for every pull request and for
  ``master`` merges. Stages typically include:

  * Dependency install + cached layers.
  * Pre-commit re-run (the same hooks as ``.githooks/pre-commit``).
  * Pyright type-check (``pyrightconfig.json``).
  * Pytest (the same suite developers run locally) with coverage
    enforced against ``coverage-floors.yml``.
  * Sonar scan publishing to the project pinned in
    ``sonar-project.properties``.
  * Sauron scan against ``.sauron.yml``.

  The build artifact is the Docker image; on a successful
  ``master`` merge the build pushes the image and the Spinnaker
  pipeline picks it up via image-tag webhook. *No build, no
  deploy* — there is no manual image-push path in steady state.

Verification anchors for the deployment surface
-----------------------------------------------

* ``Dockerfile`` — must keep ``WORKDIR`` at project root; entry
  point is gunicorn, not ``flask run``.
* ``nebulae.yml`` / ``project-descriptor.yml`` / ``alias-descriptor.yml``
  — read together; the aliases page is the canonical "what URL
  hits what env."
* ``archetype-descriptor.yaml`` — bump only via archetype tooling.
* ``default-pipelines.spinnaker.yaml`` and ``…-archetype.yaml``
  — kept in sync; drift is a signal, not a target.
* ``bitbucket-pipelines.yml`` — same checks as the local
  pre-commit; CI failures fall into one of pyright / pytest /
  coverage / Sonar / Sauron.

Runtime
=======

The runtime is a **gunicorn process** with **gevent workers**
serving a Flask application. Two facts about this combination
dominate the rest of the section:

#. **gevent must monkey-patch the standard library before any
   network-using import.** If a module imports ``socket`` /
   ``threading`` / ``ssl`` first, gevent's monkey patches will not
   apply to that module's already-bound references. Everything
   from ``requests`` to ``boto3`` to ``tritonclient.grpc`` is
   silently affected.
#. **gRPC's gevent integration must be turned on explicitly.**
   gRPC's C-extension does not pick up gevent's patched primitives
   automatically; ``grpc.experimental.gevent.init_gevent()`` is the
   one-liner that wires them up. Without it, every Triton gRPC
   call serializes through the gRPC threadpool instead of
   cooperating with the gevent loop, capping concurrency at
   threadpool size and surfacing as *coordinated* latency under
   load.

Both of these run in ``src/gunicorn.conf.py``, *before* gunicorn
imports the app module.

``src/gunicorn.conf.py`` — boot-time patching
---------------------------------------------

The first ~9 lines of this file are load-bearing and ordered:

#. ``from gevent import monkey; monkey.patch_all()`` — at module
   import time, before any other import that touches the network
   stack.
#. ``import grpc.experimental.gevent`` then
   ``grpc.experimental.gevent.init_gevent()`` — turns on the gevent
   path inside grpc-core. *This call must come after monkey-patch
   and before the first gRPC client is constructed.*
#. Only after the two steps above does the file (or the entry
   point that imports it) pull in application modules.

Beyond the patching prelude, ``gunicorn.conf.py`` declares the
gunicorn settings as module-level variables (the convention
gunicorn picks up when invoked with ``-c gunicorn.conf.py``):

* ``worker_class = "gevent"`` — required to make the patched
  cooperative scheduling actually do something. Sync workers would
  block per-request, defeating the patch.
* ``workers`` — a count derived from the available CPU. The exact
  value comes from the file; what matters operationally is that
  it is *not* dynamically resized: changing the worker count is a
  rolling restart, not a runtime knob.
* ``worker_connections`` — the per-worker greenlet ceiling. With
  gevent the in-flight greenlet count *is* the concurrency
  ceiling; this is why the HTTP pool exhaustion runbook treats
  saturation here as load, not as a bug.
* ``timeout`` — the gunicorn worker watchdog timeout. A worker
  that does not yield to the master within this window is killed
  and respawned. Set high enough that a slow downstream call
  (Triton gRPC up to ~6s, AI Gateway up to its own retry budget)
  does not trigger a worker kill.
* ``logconfig = "gunicorn-log.conf"`` — the file-based logging
  configuration loaded by gunicorn (see `Logging plumbing`_).

The combined effect is a single Python process per worker, each
running a single Flask app instance, multiplexing many concurrent
requests as gevent greenlets. The number of *processes* is
``workers``; the per-process concurrency is bounded by
``worker_connections`` and (independently) by the size of the
gevent pools the application code creates (see :ref:`inf-models`,
``inference_pool_size`` / ``DEFAULT_MAX_POOL_SIZE = 20``).

Why ``init_gevent()`` matters in practice
-----------------------------------------

The Triton gRPC client (``triton_grpc_client.py`` —
``InferenceServerClient(url=..., ssl=True)``) and the OpenAI-compat
HTTP client (``triton_openai_api_client.py`` — ``requests``) both
benefit from gevent cooperation. The HTTP path gets it for free
through the ``socket`` monkey-patch; the gRPC path gets it *only*
through ``grpc.experimental.gevent.init_gevent()``. If that line
is dropped, every Triton gRPC call holds a thread for ~6 seconds
in the worst case (the ``client_timeout=6`` from
``triton_grpc_client.py`` — see :ref:`inf-models`), and the
worker's effective gRPC concurrency collapses to the number of
threads in gRPC's internal pool.

This is the most common cause of a "Triton looks fine, but our p99
spiked" misdiagnosis after a refactor that touched the boot path.

Logging plumbing
----------------

* ``gunicorn-log.conf`` — gunicorn's own logging.config-style
  configuration. Wires gunicorn's access and error loggers to
  formatters and handlers. The *format* is what feeds the
  Atlassian log pipeline; do not "improve" the format without
  checking what the pipeline expects.
* ``src/gunicorn_logger.py`` — a Python module that customizes
  gunicorn's ``Logger`` class (or installs filters/handlers) so
  application log records and gunicorn's own access lines render
  consistently. This is the seam where request IDs, traceparent
  headers, and other context are stitched into the log line.
* ``src/micros_logging.py`` — the Atlassian-Micros-aware logging
  bootstrap for the application code (i.e. *not* gunicorn's own
  logs). It is what controllers, services, and the inference layer
  use when they emit ``logger.info(...)`` / ``logger.error(...)``.
  The output is structured (JSON-ish) so the Micros log pipeline
  parses fields rather than free text.

Operationally the three files form a chain: gunicorn loads
``gunicorn-log.conf`` → ``gunicorn-log.conf`` references handlers
configured by ``gunicorn_logger.py`` → application logs flow
through ``micros_logging.py`` and are emitted on the same
stdout/stderr that the Micros agent tails. A misconfiguration in
any one of them surfaces as *missing log lines*, not as a crash.
The most common failure mode is a logger name typo causing a
record to fall through to the root logger and be dropped by an
overly aggressive root-level filter.

``.flaskenv``
-------------

A developer-only file consumed by ``python-dotenv`` /
``flask run`` to set ``FLASK_APP``, ``FLASK_ENV``, and similar
variables when running the app locally outside of gunicorn. The
deployed gunicorn process does **not** read ``.flaskenv``;
production environment variables come from ``nebulae.yml`` and
the Micros secrets binding.

Two pitfalls:

#. ``.flaskenv`` can drift from production reality (e.g. a feature
   flag enabled there but not in ``nebulae.yml``). Treat it as a
   developer convenience, not as a source of truth.
#. ``flask run`` does *not* invoke ``gunicorn.conf.py``, so it
   does *not* run the gevent monkey-patch or
   ``init_gevent()``. Triton gRPC behaviour under ``flask run``
   is therefore not representative of production. See
   :ref:`getting-started` for the local-mode caveats.

Environment-variable inventory at deploy time
---------------------------------------------

The full set of environment variables the running process expects
is the union of:

* The ``env:`` block of the active ``nebulae.yml`` profile (per
  environment).
* Variables resolved from secret bindings declared in the same
  file (database URIs, ASAP signer keys, AI-Gateway credentials,
  AWS access for the SageMaker assume-role fallback in
  ``sagemaker_base.py``).
* Defaults baked into ``src/config.py`` and consumed at first
  import — see :ref:`config-overview` for the authoritative list.

When :ref:`config-overview` introduces a new variable, this page
does not need an update unless the variable becomes load-bearing
for a runbook step (e.g., a new dashboard URL pointer or a new
toggle that changes a fail-open default). The cross-reference is
*one-way*: ``operations`` points readers at ``config-overview``
for the inventory; ``config-overview`` is the source of truth.

Verification anchors for the runtime
-------------------------------------

* ``src/gunicorn.conf.py`` — first lines: ``monkey.patch_all()``
  before everything; ``grpc.experimental.gevent.init_gevent()``
  next; only then any other import. ``worker_class = "gevent"``.
* ``gunicorn-log.conf`` — declares formatters/handlers/loggers in
  the standard ``logging.config`` file format.
* ``src/gunicorn_logger.py`` — module-level ``Logger`` subclass
  or handler installer referenced from ``gunicorn-log.conf``.
* ``src/micros_logging.py`` — application-side bootstrap; emits
  structured records on stdout for the Micros log tail.
* ``.flaskenv`` — developer-only; not in the production boot
  path.

Quality gates
=============

The merge gate to ``master`` is layered: locally enforced by
pre-commit hooks, remotely enforced by Bitbucket Pipelines + Sonar
+ Sauron, and statistically enforced by per-module coverage floors.
Most of these are pure *configuration*: the rules live in source,
the enforcement is owned by the tooling.

Pre-commit chain
----------------

* ``.pre-commit-config.yaml`` — the canonical hook configuration
  consumed by ``pre-commit``. Hook examples typically include:
  formatter (black / ruff format), linter (ruff or flake8), import
  sorter, type-check (pyright in pre-commit mode), pytest fast
  subset, and YAML / JSON validators.
* ``.githooks/pre-commit`` — a thin shell script that *invokes*
  ``pre-commit run --hook-stage commit`` on staged files. It is
  installed by a developer-bootstrap step (typically
  ``git config core.hooksPath .githooks``) so that the
  repository's hook is used in place of any user-global default.
  The script is what makes ``git commit`` actually fail locally
  on a hook violation rather than falling back to "no hook
  configured."

Operationally: a CI pipeline run rerunning the pre-commit hooks is
the *redundant* check, not the primary one. Developers who skip
the local hook will still be caught in CI, but they will discover
trivial format errors only after a slow remote run; the local
hook is what keeps the inner loop fast.

Static type checking
--------------------

``pyrightconfig.json`` — pyright's project configuration:

* ``include`` / ``exclude`` lists set the type-check scope —
  typically the application code under ``src/`` and the test tree.
  Files outside the include list are not type-checked even if they
  exist.
* ``reportMissingTypeStubs``, ``strictListInference``,
  ``reportGeneralTypeIssues`` and friends set the strictness. The
  exact tier (``basic`` / ``standard`` / ``strict``) is what
  determines whether an unannotated parameter is a hard error or
  a hint.
* ``executionEnvironments`` may pin a specific Python version /
  ``extraPaths`` so that imports resolve correctly under the
  same layout the production wheel uses.

Pyright runs in CI (Bitbucket Pipelines) and locally in the
pre-commit hook. The two share ``pyrightconfig.json`` so a passing
local check is a representative signal.

Coverage floors
---------------

* ``.coveragerc`` — coverage.py's runtime configuration: which
  source paths to measure, which to exclude (tests, generated
  code, vendored dependencies), and how to render reports. This is
  what determines *what* the coverage number is computed over.
* ``coverage-floors.yml`` — the *enforcement* layer: a per-module
  table of minimum acceptable coverage percentages. Failing any
  one row fails the CI step. The goal is not to track an aggregate
  number but to fence specific subtrees against regression. The
  inference layer, the moderation service, and the
  ``app_context.py`` boot path are the kinds of modules whose
  floors are non-negotiable; thin glue modules tolerate lower
  floors.

Bumping a floor *up* is encouraged after a coverage improvement.
Bumping a floor *down* should always be paired with a comment
linking to the change that justified it (a refactor, an exception
class deletion, etc.) — otherwise the file silently records
backsliding.

Sonar
-----

``sonar-project.properties`` — Sonar project key, organization,
sources / tests roots, language version, and any local override of
the centrally configured quality profile. Sonar consumes the same
coverage report ``.coveragerc`` produces (typically
``coverage.xml``) and adds its own duplications / smells / hotspots
checks on top. The Sonar quality gate is independent of
``coverage-floors.yml``: it checks code on the *new* lines (delta
coverage), not on the absolute per-module floors.

Sauron
------

``.sauron.yml`` — Sauron is Atlassian's configuration scanner. It
checks for hard-coded secrets, missing license headers, banned
dependencies, and similar policy items. The rules in ``.sauron.yml``
are *project-local overrides* of platform defaults: typically a
small allow-list for false positives, and any explicit opt-ins for
stricter checks the team adopts.

When Sauron flags a finding in CI, the resolution is one of:

* Fix the underlying issue (the common case — a leaked secret, a
  missing header).
* Add a justified, dated entry to ``.sauron.yml`` with a comment.
* Bump the dependency or remove it.

Do *not* disable a rule globally to silence a single finding.

``bin/`` scripts
-----------------

The ``bin/`` directory holds operational shell scripts that are
referenced from runbooks, the CI pipeline, and developer
bootstrap. A representative subset:

* ``bin/start-app-locally.sh`` — local production-shaped boot.
  Launches gunicorn with ``-c src/gunicorn.conf.py`` from the
  project root so the gevent + gRPC patching path runs the same
  way it does in production. This is the script :ref:`inf-models`
  references when explaining the working-directory dependency.
* ``bin/<test or coverage helper>`` — wraps ``pytest`` with the
  ``.coveragerc`` and ``coverage-floors.yml`` checks so the local
  command matches CI exactly.

Treat ``bin/`` as part of the merge gate: a script change that
breaks ``bin/start-app-locally.sh`` will not surface in CI (CI
does not run it), but it will surface as developer pain and as a
runbook that no longer works.

Verification anchors for the quality gates
------------------------------------------

* ``.pre-commit-config.yaml`` plus ``.githooks/pre-commit`` —
  hooks listed in the YAML are what the shell script runs.
* ``pyrightconfig.json`` — ``include`` / ``exclude`` define the
  type-check scope; same config in CI and locally.
* ``.coveragerc`` defines what's measured; ``coverage-floors.yml``
  defines what's enforced.
* ``sonar-project.properties`` — project key, org, paths.
* ``.sauron.yml`` — project-local override of platform Sauron
  policy; allow-list entries should carry a justification comment.
* ``bin/`` — operational scripts; ``bin/start-app-locally.sh`` is
  the canonical local boot.

.. _ops-overview:

Operational runbooks
====================

Three runbooks are documented here. They are the failure modes
that have specific upstream / downstream coupling to this service
and that on-call needs a *deterministic* response for. Other
incidents (image-build failures, CI flakes, transient deploy
errors) are common-platform problems and are handled by the
generic Atlassian Micros / Spinnaker runbooks; pointers are in
`Monitoring & alerting hooks`_.

Each runbook follows the same shape:

* **Trigger** — the precise condition that causes the symptom. A
  named line of source code wherever possible.
* **Symptoms** — what the on-call sees first (alerts, metrics,
  log lines).
* **Diagnostic queries** — what to look at, in order, before
  acting.
* **Mitigation** — the smallest change that returns service.
* **After** — what to verify before closing the incident.

Runbook: HTTP pool exhaustion
-----------------------------

**Trigger.** The application's HTTP client pool — initialized via
``default_http_config`` at ``app_context.py:47`` — has a **5-second
``pool_timeout``**. When in-flight HTTP requests (the AI Gateway
path, plus any other ``httpx``-backed downstream) exceed the pool
ceiling, new requests block waiting for a free connection. After
5 seconds the wait raises a ``httpx.PoolTimeout``.

This is *not* a downstream failure. The AI Gateway may be perfectly
healthy; the symptom is that this service is not consuming its
responses fast enough to free pool slots.

**Symptoms** (in the order they typically appear):

#. p99 latency on the moderation endpoint rises sharply, with the
   p50 mostly unchanged at first.
#. ``httpx.PoolTimeout`` (or its retry-wrapped equivalent) shows
   up in error logs from the moderation service path. Per
   :ref:`inf-models`, the AI Gateway path's tenacity retry
   (``app_context.custom_retry_config``) only retries on
   ``httpx.TimeoutException`` and ``httpx.NetworkError`` — pool
   timeouts may not be retried, so each pool-saturated request
   surfaces as one user-visible 500 / 503.
#. The gunicorn worker connection count climbs toward
   ``worker_connections``. Workers continue to accept requests
   (gevent is cooperative) but the queue depth grows.
#. If the saturation persists, gunicorn's worker watchdog
   ``timeout`` will start killing workers that have not yielded
   to the master in time, causing rolling restarts that look like
   instability rather than load.

**Diagnostic queries** (the order is the diagnostic; deviating
from it tends to misdiagnose the cause):

#. **Is the *AI Gateway* itself slow?** Compare AI-Gateway
   server-side latency dashboards (the dashboards live with the
   AI-Gateway team — see `Operational ambiguities`_ for the URL
   gap) with this service's client-side latency. A gap
   ("downstream is fast, we are slow") confirms pool exhaustion
   rather than upstream slowness.
#. **Is the inflight count climbing?** The metrics emitted
   through ``micros_logging.py`` / structured logs include
   gunicorn worker connection counts and per-route inflight
   gauges. Climbing inflight + flat downstream latency = pool
   exhaustion.
#. **Are the retries firing?** Per :ref:`inf-models`, the AI
   Gateway tenacity config retries timeouts but not 429s. A spike
   in retried requests amplifies pool pressure (each retry holds
   another slot). If retries are spiking, the pool-pressure cause
   is *upstream* even though the trigger is local.
#. **Is the gevent pool full?** The image-moderation path and the
   model-shadowing path each have *their own* gevent ``Pool`` (see
   :ref:`inf-models`, ``inference_pool_size`` and
   ``DEFAULT_MAX_POOL_SIZE = 20``). They short-circuit silently
   when full (``logged at warning``, no metric event by default).
   Look for those warnings — if they precede the pool exhaustion
   they are evidence the load is image-side, not text-side.

**Mitigation** (lowest-risk first):

#. **Identify a slow downstream first.** If an AI-Gateway-side
   incident is in progress (see `Runbook: AI Gateway upstream
   incidents`_), the *correct* response is to follow that runbook
   — not to scale this service. Adding workers to a service whose
   downstream is the bottleneck makes the downstream *more*
   saturated.
#. **Scale workers horizontally.** Bump replica count via the
   Helm values (``replicas`` or the Micros equivalent in
   ``nebulae.yml``). Horizontal scale is the right shape because
   each replica brings its own HTTP pool — you are increasing
   the system's pool capacity proportionally.
#. **Vertical scale only if the per-pod CPU is saturated.** A
   gevent worker that is CPU-bound (e.g. tokenization on a giant
   prompt) will not yield, and adding pool slots only buys queue
   depth. CPU saturation is visible per-pod in the Micros
   dashboards.
#. **Last resort: enable the fail-open feature flags.** If
   ``should_fail_open_on_model_timeout`` is *not* already on, the
   sustained timeouts will surface as user-visible errors. Turning
   it on (per :ref:`config-overview`) returns conservative
   verdicts (score ``0.5`` for timeouts) without blocking. This
   is a *load* mitigation, not a *correctness* one — flip back
   off after the incident.

**After.** Verify the inflight gauge has returned to baseline,
the pool-timeout error rate is at zero, and the canary on any
in-progress deploy has resumed (`Spinnaker pipelines`_). File a
follow-up if the trigger was self-induced (e.g. a regression in
this service's request shape) so the relevant downstream caller
can be tightened.

Runbook: gRPC circuit breaker recovery
---------------------------------------

**Trigger.** The Triton gRPC client (``triton_grpc_client.py``)
wraps each invocation in
``pybreaker.CircuitBreaker(name="triton_circuit_breaker", fail_max=30)``
— see :ref:`inf-models`. After 30 consecutive failures the
breaker opens; subsequent calls raise
``pybreaker.CircuitBreakerError`` *immediately*, without hitting
the network.

The breaker is a per-instance object: ``GrpcEndpoint`` and
``TritonOpenAIClient`` each have their own ``CircuitBreaker`` with
the same name, but **state is not shared between them**. Opening
one does not open the others.

**Symptoms:**

#. Sudden cliff in successful Triton call rate, with
   ``CircuitBreakerError`` replacing the earlier transport
   exception (network timeout, ``InferenceServerException``, etc.)
   in the logs.
#. If ``should_fail_open_if_circuit_breaker_open`` is on, requests
   continue to succeed at the user-visible level but with
   ``violation_score = 0.0`` and the model-evaluation-version
   field reflecting a fail-open. This is the *quiet* failure mode
   that does not page on its own — it has to be discovered by
   watching the rate of fail-open responses.
#. If the flag is off, callers see a 503 with a circuit-breaker
   error.

**Diagnostic queries:**

#. **Which breaker is open?** The breaker name is the same for
   both transports; the *transport* is what differs. Filter logs
   by the call-site (``GrpcEndpoint.invoke`` vs
   ``TritonOpenAIClient.send_chat_completions``) to identify
   which client is shedding load.
#. **Is Triton itself unhealthy?** Triton health is owned by the
   Teamserve team. The local readiness check
   (``GrpcEndpoint.is_healthy()``) returns ``True`` only when the
   breaker is *not* in the ``open`` state — i.e. it reflects the
   client view, not the server view. A "Teamserve is fine but our
   breaker is open" disagreement points at the network path
   between this service and Teamserve, not at Triton.
#. **What was the failure cadence pre-trip?** ``fail_max=30``
   means 30 *consecutive* failures: a slow leak (failures mixed
   with successes) does not trip the breaker even at high error
   rate. A trip therefore implies a sustained failure window
   ~30 calls long.

**Recovery.** ``pybreaker``'s default reset behaviour transitions
the breaker through ``open`` → ``half-open`` after the configured
reset timeout (the value comes from the ``pybreaker`` defaults
unless overridden in the ``CircuitBreaker`` constructor — verify
against ``triton_grpc_client.py``). In the half-open state the
*next* successful call closes the breaker; a failure re-opens it.

* **No manual action is required for most trips.** If Triton
  recovered, the next probe call will close the breaker
  automatically.
* **If the breaker is open and the underlying cause is fixed
  but the breaker has not reset:** restart the affected pods.
  The breaker is held in process memory; a pod restart drops
  it. This is the only "manual reset" available — there is no
  admin endpoint that flips the breaker state.
* **If the underlying cause is not fixed:** opening the breaker
  is correct. Do *not* restart pods to "clear" the breaker
  before fixing the upstream — you will simply re-trip it after
  another 30 calls and add request-load to a recovering Triton.

**Fallback behaviour during an open breaker:**

* With ``should_fail_open_if_circuit_breaker_open`` **on**,
  failing open returns ``violation_score = 0.0``
  (``PromptHarmCategory.NONE`` from the caller's perspective).
  See :ref:`inf-models` for why ``0.0`` and not the timeout-path
  ``0.5``.
* With the flag **off**, the breaker error propagates and the
  caller sees a 503.

There is no automatic *fallback to a different model* when the
gRPC path is open. The selector in ``RAILlamaModels.get_model()``
runs *before* the call and is feature-flag-driven; it does not
re-run on a circuit-breaker error. If a deliberate, durable
fallback is needed during a Triton outage, flip the relevant
``…_primary_enabled`` flag (see :ref:`config-overview` and
:ref:`inf-models`) so the AI-Gateway path is the primary instead.

**After.** Confirm successful Triton calls are flowing again
(breaker state ``closed``) and the fail-open rate has returned
to zero. If the fail-open flag was *toggled* during the incident,
toggle it back to its incident-time-default value.

Runbook: AI Gateway upstream incidents
---------------------------------------

**Trigger.** The AI Gateway path (``msp_sdk.invoke_rai_ft_2_3_3``,
used by the legacy ``V2_3_3_prompt_v2`` variant) is failing with
sustained 5xx, network errors, or timeouts beyond what the
local retry config absorbs. Per :ref:`inf-models`, the retry
config in ``app_context.py:custom_retry_config`` does **2
attempts** with ``wait_random_exponential(multiplier=1,
min=0.5, max=1.5)``, and **only retries** on
``httpx.TimeoutException`` / ``httpx.NetworkError`` —
specifically excluding HTTP 429.

**Symptoms:**

#. ``AIGatewayResponseException`` /
   ``httpx.TimeoutException`` / ``httpx.NetworkError`` rate
   climbing in logs from the moderation service.
#. p99 latency on the AI Gateway code path increasing, with the
   Triton-path latency unchanged (since they're independent).
#. If ``should_fail_open_on_model_timeout`` is on, fail-open
   responses with ``violation_score=0.5`` showing up in
   downstream logs (the downstream caller still applies its own
   threshold to that 0.5).

**Detection.** AI Gateway is owned by a different team; the
canonical signal that *they* are in incident is their own status
page / alert channel (URL gap — see `Operational ambiguities`_).
The local signal is the elevated error rate from this service's
AI-Gateway code path.

**Diagnostic queries:**

#. **Is this service's Triton path still healthy?** If yes
   (``triton_circuit_breaker`` closed, Triton call latency
   normal), the Triton-served variants are unaffected. The
   only failing variant is ``V2_3_3_prompt_v2``.
#. **Is the affected variant the primary?** Per
   :ref:`inf-models`, ``RAILlamaModels.get_model()`` picks the
   primary based on
   ``is_prompt_moderation_teamserve_v2_4_primary_enabled`` /
   ``is_rai_ft_teamserve_primary_enabled``. If neither is on,
   the AI-Gateway variant is the primary and an AI-Gateway
   incident is a service-wide incident. If a Teamserve variant
   is on, the AI-Gateway path is only the primary for tenants
   excluded from the Teamserve flag — verify the per-tenant
   flag evaluation.
#. **Are HTTP 429s present?** 429s from AI Gateway are *not*
   retried by the local config (``_should_retry_custom_logic``
   excludes 429). A 429 surge points at *this* service hitting a
   rate-limit, not at AI Gateway being broken — the mitigation
   is to back off, not to escalate to the AI-Gateway team.

**Mitigation:**

* **Primary mitigation.** If a Teamserve variant is healthy,
  flip the relevant ``…_primary_enabled`` flag to make the
  Teamserve path the primary for all tenants (see
  :ref:`config-overview`). The selector picks up the new flag
  on the *next* request — no restart required. ``model_shadowing``
  is unaffected; if the AI-Gateway path was being used as a
  shadow it will keep failing in the shadow path, which is
  silent by design — shadow errors are swallowed in the
  pool-full-as-load-shedding pattern documented in
  :ref:`inf-models`.
* **Secondary mitigation.** Enable
  ``should_fail_open_on_model_timeout`` if not already on. This
  yields ``violation_score=0.5`` on AI-Gateway timeouts; the
  downstream caller's threshold then decides whether the
  request is filtered. This *changes the verdict distribution*
  during the incident — some requests will be admitted that
  would otherwise have been blocked. Flip back off after.
* **When to declare an incident.** If neither Teamserve variant
  is healthy *and* AI Gateway is degraded *and* fail-open does
  not produce acceptable verdicts for the downstream caller,
  the service is effectively in an outage. Page per the team's
  on-call escalation chain (see `Operational ambiguities`_ for
  the URL gap).

**After.** Confirm AI-Gateway error rate has returned to
baseline. If a flag was flipped during mitigation, decide
deliberately whether the new flag state is the *new* steady
state or whether to revert. Document either decision; "we
left ``…_primary_enabled`` on after the incident" is a
configuration drift, not an artifact, if it is not written
down.

Monitoring & alerting hooks
===========================

Visibility into this service is split across three layers:

#. **Logs.** ``micros_logging.py`` emits structured records on
   stdout that the Micros log pipeline collects. Searchable per
   request ID, per route, per logger name. The shadowing
   evaluator (see :ref:`inf-models`, ``RAIModelShadowEvaluator``)
   emits its comparison output on this channel only — there is
   no Kafka / S3 / analytics emission for shadowing.
#. **Metrics.** Numeric signals emitted through the Micros
   metrics pipeline. The metrics that the runbooks above
   reference:

   * Gunicorn worker connection count and per-route inflight
     gauges (`Runbook: HTTP pool exhaustion`_).
   * Triton call success / error rate, breaker state
     (`Runbook: gRPC circuit breaker recovery`_).
   * AI-Gateway success / error rate, latency histogram
     (`Runbook: AI Gateway upstream incidents`_).
   * Fail-open counters (one per fail-open flag) — the rate of
     these is the single most important "is this incident
     user-visible?" signal.
#. **Traces.** Per-request OpenTelemetry traces propagated via
   ``contextvars.copy_context()`` into spawned greenlets in
   the image-moderation and shadowing paths
   (see :ref:`inf-models`).

**Dashboards & alerts.** The dashboards that consume the metrics
above, and the alerts that fire on them, live in the team's
observability tooling (Datadog / SignalFx / Atlassian's internal
metrics UI — exact platform varies by team and is not
discoverable from this source tree). The runbook entries above
deliberately do not include URLs because a stale URL in source
is worse than no URL — see `Operational ambiguities`_.

What the metrics & analytics feed *do not* cover:

* **Shadowing comparison output.** The
  ``RAIModelShadowEvaluator`` writes only ``logger.info`` lines
  — comparing primary and candidate model outputs requires
  running a log query, not opening a dashboard. This is by
  design (see :ref:`inf-models`, *Why ``model_shadowing``
  exists*).
* **Per-tenant verdict drift.** Confidence thresholds are
  per-tenant (see :ref:`inf-models`,
  ``confidence/confidence_thresholds.py``); a per-tenant
  spike in fail-opens, a tenant whose threshold lookup is
  silently falling back to ``DEFAULT_CONFIDENCE_THRESHOLD =
  0.5`` because the dynamic-config payload is missing — these
  are not aggregated as metrics today and require
  log-based investigation.

**On-call escalation chain.** The downstream caller of this
service has its own on-call rotation; AI Gateway has its own;
Teamserve has its own. The escalation chain that ties them
together is *not* in this repository. See `Operational
ambiguities`_.

Operational ambiguities
=======================

The following items are **not** derivable from the source tree
and are deliberately left as gaps in this page rather than
guessed at:

.. list-table:: Gaps and where to fill them
   :header-rows: 1
   :widths: 32 38 30

   * - Gap
     - Why it's not in source
     - How to resolve
   * - Dashboard URLs
     - Dashboards are owned in observability tooling, not in
       this repo; URLs there are mutable and would rot here.
     - Add as a team-internal pointer (Confluence /
       internal wiki) and link from the runbook descriptions.
   * - On-call rotation / page numbers
     - Owned by Opsgenie or equivalent; not in source.
     - Same — internal pointer.
   * - AI Gateway team's status / incident channel
     - External owner; not in source.
     - Internal pointer to the upstream team's status page.
   * - Teamserve / Triton ownership for the
       ``teamserve-rai-optimized-logits`` model
     - Cross-team boundary; the model name is in source
       (``triton_grpc_client.py``) but the owning team is not.
     - Internal pointer; see :ref:`inf-models`,
       *Why two Triton client variants exist*.
   * - Exact ``pybreaker`` reset timeout value
     - Defaults from ``pybreaker`` unless explicitly set in
       the ``CircuitBreaker`` constructor; check
       ``triton_grpc_client.py`` and update if overridden.
     - Update the gRPC circuit breaker runbook with the precise
       timeout when verified against source.
   * - Spinnaker pipeline canary thresholds
     - Owned by the archetype; not in this repo's
       ``default-pipelines.spinnaker.yaml`` unless overridden.
     - Reference the archetype version in
       ``archetype-descriptor.yaml`` and link to the
       archetype's documentation.

Filling these gaps does **not** require editing this page; an
internal-pointer link maintained in the team's runbook hub is
enough. Avoid pasting URLs directly into this Sphinx page —
they will outlive the underlying resource.

Cross-references
================

Backward
--------

* :ref:`getting-started` — local-vs-deployed run modes,
  developer bootstrap, and the caveats around ``flask run`` not
  exercising the gevent / gRPC patching path.
* :ref:`architecture` — the wiring diagram, including how
  ``app_context.get_prompt_moderation_service`` constructs the
  service graph at startup. The deployment surface above is the
  outer ring of that diagram.

Forward
-------

* :ref:`config-overview` — the authoritative inventory of
  environment variables and feature flags consulted at startup,
  including the fail-open flags
  (``should_fail_open_on_model_timeout``,
  ``should_fail_open_if_circuit_breaker_open``,
  ``is_custom_retry_config_enabled``) and the per-variant
  primary / shadow flags referenced from the AI Gateway and
  circuit-breaker runbooks.
* :ref:`inf-models` — the model-side failure modes the runbooks
  address: the
  ``pybreaker.CircuitBreaker(name="triton_circuit_breaker",
  fail_max=30)`` definition, the gevent ``Pool`` short-circuit
  behaviour, the tenacity retry config, and the fail-open
  policy.

Verification anchors
====================

The following claims were verified against source or against the
established conventions documented elsewhere on this page set.
Each entry points to the file and a representative location so a
reader can check by hand.

* ``Dockerfile`` — ``WORKDIR`` is project root; entry point is
  gunicorn invoked with ``-c src/gunicorn.conf.py``.
* ``nebulae.yml`` — runtime contract per environment; references
  secrets and resource limits.
* ``project-descriptor.yml`` / ``alias-descriptor.yml`` /
  ``archetype-descriptor.yaml`` / ``env_nebulae.json`` — Micros
  descriptors; bumped together; archetype is centrally owned.
* ``default-pipelines.spinnaker.yaml`` and
  ``default-pipelines.spinnaker-archetype.yaml`` — paired;
  drift is a signal.
* ``bitbucket-pipelines.yml`` — runs the same checks the
  pre-commit hook does, plus image build and publish.
* ``src/gunicorn.conf.py`` —
  ``from gevent import monkey; monkey.patch_all()`` is the
  *first* effective line; ``grpc.experimental.gevent.init_gevent()``
  follows; only then any application import.
  ``worker_class = "gevent"`` is required.
* ``gunicorn-log.conf`` / ``src/gunicorn_logger.py`` /
  ``src/micros_logging.py`` — the three-file log chain;
  misconfiguration surfaces as missing log lines.
* ``.flaskenv`` — developer-only.
* ``coverage-floors.yml`` — per-module floors; failing one row
  fails CI.
* ``.coveragerc`` — what's measured.
* ``pyrightconfig.json`` — type-check scope and strictness.
* ``sonar-project.properties`` — Sonar project key + paths;
  delta-coverage gate independent of ``coverage-floors.yml``.
* ``.sauron.yml`` — project-local override of platform Sauron
  policy.
* ``.pre-commit-config.yaml`` plus ``.githooks/pre-commit`` —
  the hooks the script runs.
* ``bin/start-app-locally.sh`` — canonical local
  production-shaped boot.
* ``app_context.py`` —
  ``default_http_config`` at line 47 sets a 5-second
  ``pool_timeout``; ``custom_retry_config`` defines tenacity
  with 2 attempts and ``wait_random_exponential(0.5–1.5s)``,
  retrying only ``httpx.TimeoutException`` /
  ``httpx.NetworkError`` (excludes 429). See :ref:`inf-models`
  for the retry config's call-site coupling.
* ``triton_grpc_client.py`` —
  ``pybreaker.CircuitBreaker(name="triton_circuit_breaker",
  fail_max=30)`` per ``GrpcEndpoint`` instance; state not
  shared across transports despite shared name. See
  :ref:`inf-models` for the full transport contract.
