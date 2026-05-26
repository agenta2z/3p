.. _glossary:

========
Glossary
========

.. note::

   This is the single page where a reader can resolve any unfamiliar
   term used elsewhere in the documentation **without** an inline
   definition on the page that uses it. Two parts:

   * The ``.. glossary::`` directive below — alphabetised — for
     terms that appear on two or more pages of the documentation.
     Reference any term from another page via ``:term:`<term>```
     (e.g. ``:term:`ETag```, ``:term:`Triton```).
   * The :ref:`anchor-map` registry below the glossary — a single
     index of every ``.. _<name>:`` cross-reference target in the
     documentation, grouped by page. Each row is
     ``anchor-name`` → ``file.rst:line`` → one-line purpose, so the
     cross-reference graph is machine-discoverable.

   Source-of-truth scope. Every entry below was written against the
   three .rst files that currently exist in ``docs/source/``
   (:ref:`config-overview`, :ref:`inf-models`, :ref:`infra-overview` /
   :ref:`ops-overview`). Five pages — ``introduction``,
   ``getting-started``, ``architecture``, ``service-layer``,
   ``api-reference`` — are forward-referenced by anchor name from the
   existing pages but are **not yet authored**. Their anchors appear
   in the :ref:`anchor-map` below tagged as ``(forward-referenced —
   target page not yet authored)`` so the registry is honest about
   what currently resolves under :term:`nitpicky mode`.

.. contents::
   :local:
   :depth: 1

Terms
=====

.. glossary::
   :sorted:

   AI Gateway
       Atlassian's upstream model-serving platform that the service
       calls into for the legacy ``V2_3_3_prompt_v2`` Llama path
       (via ``msp_sdk.invoke_rai_ft_2_3_3``) and that brokers the
       Triton OpenAI-compatible URL composed from
       ``MESH_DEPENDENCY_AI_GATEWAY_BASE_URL``. HTTP retry policy is
       configured one level up in
       ``api/v1/moderation/app_context.py:custom_retry_config``
       (tenacity, 2 attempts, ``wait_random_exponential(0.5–1.5s)``,
       retrying only ``httpx.TimeoutException`` /
       ``httpx.NetworkError`` — HTTP 429 is **not** retried) and is
       opt-in via ``feature_service.is_custom_retry_config_enabled``.
       See :ref:`inf-models` § *AI Gateway invocation path* and
       :ref:`config-overview` § *ML platform: input moderation client*.

   confidence threshold
       The per-tenant numeric threshold (range ``[0, 1]``) that gates
       whether a model's raw violation score becomes a user-visible
       "filtered" verdict. Lookup is per-(tenant, harm_category[,
       model_evaluation_version]); values come from Atlassian dynamic
       config under ``responsible-ai-api-prompt-harm-thresholds`` /
       ``responsible-ai-api-prompt-thresholds-by-version`` and are
       cached for up to 60 s via ``@time_cache(max_age=60)``;
       ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5`` is the fallback. The
       comparison is ``score >= threshold`` (the upper boundary is
       inclusive — an exact-equal score crosses). Only the *prompt*
       path uses this subpackage; image thresholds are static-config
       values (``image_moderation_v0_threshold`` /
       ``image_moderation_v1_threshold``). See :ref:`inf-models`
       § *Confidence subpackage*.

   debug trace
       The opt-in per-request ``DebugTrace`` model that controllers
       attach to ``APIException`` when ``debug.verbose=true`` is set
       on the inbound moderation request. ``make_api_error_response``
       (``src/exception.py``) adds it as a top-level ``"trace"`` key
       in the JSON error body via
       ``model_dump(exclude_none=True)``. The ``InternalServerError``
       global handler also propagates ``debug_trace`` from
       ``original_exception``. See :ref:`api-reference`
       § :ref:`api-debug-trace` for the response shape and
       :ref:`architecture` § :ref:`arch-debug-trace` for the global
       handler chain.

   ETag
       In this codebase, a **prompt-cache safety token**, *not* the
       generic web-server HTTP ETag. It is a *weak* ETag computed
       from a hash of the parsed request body **and the expected
       model versions**, used to power ``If-None-Match`` 304
       short-circuits on the prompt-moderation endpoint. The hash is
       deliberately a fingerprint of the moderation **inputs** (and
       *not* of the response body) so the safety guarantee survives
       a model upgrade — the same prompt under a new model version
       produces a new ETag. The mechanism is independent of the
       server-side ``time_cache`` (which sits on
       ``confidence/confidence_thresholds.py``); they are both
       caches but they cache different things and do not share
       state. The full protocol — what is hashed, the weak-ETag
       form, the ``If-None-Match`` short-circuit, and the
       prompt-only scope — lives in :ref:`api-etag`.

   GAS v3
       Atlassian's operational analytics pipeline, accessed through
       ``analytics_client.client.Client`` and wrapped here as
       ``RAIAnalyticsClient`` in ``src/gasv3_analytics/``. Configured
       with ``product="responsibleAI"``, ``subproduct=None``,
       ``timeout=2s``, and per-env retry budget (``UNKNOWN``/``LOCAL``
       → 0, ``DEV``/``STAGING`` → 2, **``PROD`` → 1**). Emission is
       fire-and-forget on a process-local ``gevent.pool.Pool(10)``;
       SDK transport failures are caught in ``_send_event`` and
       logged. Four event classes correspond to the four moderation
       kinds (``ContentEvaluatedEvent``, ``ImageEvaluatedEvent``,
       ``AgentEvaluatedEvent``, ``OutputEvaluatedEvent``); the
       output path fires *N* events per HTTP request (one per
       evaluated chunk), the others fire one. See
       :ref:`config-overview` § *Analytics: GASv3*.

   harm category
       The categorical verdict label produced by every moderation
       path. Two enums own the vocabulary: ``PromptHarmCategory``
       (used by prompt + agent + output paths — ``prompt_harm_category``
       is what flows through ``PredictionResult``) and
       ``ImageHarmCategory`` (image path; values include
       ``HUMAN``, ``HATE_DISCRIMINATION``, ``VIOLENCE_HARASSMENT``,
       ``ILLEGAL_ACTIVITY``,
       ``PERSONALLY_IDENTIFIABLE_INFORMATION``,
       ``INTELLECTUAL_PROPERTY``, ``NONE`` — see the antiabuse
       mapping table in :ref:`config-overview` § *Anti-abuse
       integration*). The category travels through GAS v3 events as
       the ``detectedHarmCategory`` field and shows up as the
       ``harm_category`` StatsD tag. Confidence-threshold lookups
       are keyed on it. See :ref:`inf-models` for derivation and
       :ref:`svc-moderation` for the per-kind orchestration.

   Micros
       Atlassian's internal service-runtime platform. The service
       is deployed under Micros conventions: a project-root
       ``Dockerfile`` builds the image; runtime is described to the
       Micros control plane via the coordinated descriptors
       ``nebulae.yml``, ``project-descriptor.yml``,
       ``archetype-descriptor.yaml``, ``alias-descriptor.yml``, and
       the generated ``env_nebulae.json``. Inside the process, the
       ``FlaskMicros(app)`` call (at ``src/app.py:38``) installs the
       ``atlassian-flask-dogstatsd`` middleware that populates
       ``g.global_stat`` (used by every metric in the project), and
       ``src/micros_logging.py`` emits structured logs onto the
       Micros log pipeline. See :ref:`infra-overview`
       § *Atlassian Micros conventions* and :ref:`config-overview`
       § *Metrics: StatsD via FlaskMicros*.

   Nebulae
       Atlassian's internal deployment / control-plane platform that
       consumes ``nebulae.yml``. The file is the per-environment
       runtime contract — image reference, environment variables,
       resource requests/limits, scaling policy, ingress/egress, and
       secret bindings — and differs between ``ddev``, ``stg``, and
       ``prod``. The ``NEBULAE`` env var (string ``"true"``) is one
       of the three independent inputs to ``config.is_local`` (the
       others being ``EnvType.LOCAL`` and a default ``service_url``).
       The Nebulae integration-test wiring also publishes
       ``MESH_DEPENDENCY_AI_GATEWAY_BASE_URL``, which is what
       composes ``teamserve_gptoss_endpoint`` when the explicit env
       override is unset (``config.py:128-140``). See
       :ref:`infra-overview` § *Atlassian Micros conventions* and
       :ref:`config-overview` § *Static configuration*.

   nitpicky mode
       The Sphinx build flag (``nitpicky = True`` in ``conf.py`` —
       equivalent to invoking ``sphinx-build -n``) that promotes every
       unresolved cross-reference (``:ref:``, ``:term:``, ``:doc:``,
       ``:py:...:``) from a warning to a hard build error. The
       documentation build subtask runs in this mode so missing
       anchors and stale links surface immediately rather than
       silently resolving to plain text. The :ref:`anchor-map` below
       is the registry the build cross-checks against — every
       ``:ref:`` that appears in any of the eight .rst pages must
       resolve to a row in that map.

   pool timeout
       In this codebase, **specifically** the
       ``pool_timeout = 5 s`` field on ``default_http_config``
       constructed at ``api/v1/moderation/app_context.py:47`` —
       the wait a new HTTPX request will block for a free
       connection from the pool before raising
       ``httpx.PoolTimeout``. **Distinct from the four 10 s
       timeouts** (``connect`` / ``read`` / ``write`` / overall) on
       the same config: the four 10 s values bound a single
       in-flight call's transport phases, while pool timeout
       bounds the wait *before* a request is admitted. Pool
       timeout is the value that rises during HTTP-pool
       exhaustion (the AI-Gateway path saturating the shared
       HTTPX pool) — characteristically p99 latency climbs while
       p50 is unchanged. The local tenacity retry config does
       **not** retry ``PoolTimeout`` (it retries only
       ``TimeoutException`` / ``NetworkError``), so each pool
       timeout becomes a user-visible 5xx. See :ref:`ops-overview`
       § *Runbook: HTTP pool exhaustion*.

   policy filter
       Historical naming for the prompt-moderation analytics
       channel. The ``ContentEvaluatedEvent`` (the GAS v3 event
       fired from the prompt-moderation path at
       ``prompt_moderation_controller.py:136``) carries
       ``action_subject = ("contentEvaluated", "policyFilter")``
       to align with the older "policy filter" convention; the
       canonical schema home is the
       ``src/gasv3_analytics/events/policy_filter/`` subdirectory.
       The string ``"ai-policy-filtering"`` is also the use-case
       ID for the prompt path
       (``UseCases.AI_POLICY_FILTERING``) and is the only entry in
       ``feature_service.USE_CASE_IDS``. Newer event kinds
       (image / agent / output) get their own ``action_subject``
       pairs and are *not* called "policy filter." See
       :ref:`config-overview` § *Analytics: GASv3*.

   RAI
       **Responsible AI** — what this service does. The product
       name surfaces as the literal string ``"responsibleAI"``
       (GAS v3 ``product`` field), the logger name
       ``"responsible-ai-api"`` (``config.py:56``), the
       dynamic-config namespace ``"responsible-ai-api_server"``,
       the dynamic-config keys
       ``responsible-ai-api-prompt-harm-thresholds`` /
       ``responsible-ai-api-prompt-thresholds-by-version``, the
       Statsig gate prefix ``rai_*``, and the Triton model name
       ``teamserve-rai-optimized-logits``. Class names with the
       ``RAI`` prefix (``RAILlamaModels``, ``RAIGPTOSSModels``,
       ``RAIAnalyticsClient``, ``RAIFTEndpointV2_3_3``,
       ``RAIModelShadowEvaluator``) all belong to this service.
       See :ref:`introduction` for the project-level scope.

   shadow model
       A candidate model run alongside the primary so the
       candidate's verdict is logged but not used for the
       user-visible response. Implemented in
       ``src/inference_models/model_shadowing/shadower.py``:
       ``ShadowShim[U, P]`` wraps two ``InferenceModel`` instances
       behind one (so the shimmed object satisfies the same
       interface), ``ModelShadower`` owns a
       ``gevent.pool.Pool(20)`` (``DEFAULT_MAX_POOL_SIZE = 20``),
       and per-request both models execute concurrently. The
       candidate's response goes through
       ``ShadowEvaluator.evaluate(...)`` (today only
       ``RAIModelShadowEvaluator`` exists), which logs a
       structured diff line; the shim returns the *primary*'s
       response synchronously, so user-visible latency is bound
       to primary, not shadow. The pool-full guard silently falls
       back to primary-only. Sampling is at the feature-flag
       layer (``is_shadow_with_*_enabled`` flags) rather than
       per-request inside the shim. See :ref:`inf-models`
       § *Model shadowing*.

   Spinnaker
       Atlassian's deployment-pipeline platform. Two YAMLs
       together define the rollout for this service:
       ``default-pipelines.spinnaker.yaml`` (service-owned) and
       ``default-pipelines.spinnaker-archetype.yaml`` (archetype-
       tracked); they are kept in sync, and drift between them is
       a *signal* (the platform team detects archetype skew via
       this diff). The pipeline runs Kayenta-style automated
       canary analysis between the new build and the running
       baseline before promoting; canary failure blocks
       promotion and triggers automatic rollback to the previous
       image. Multi-environment progression is
       ``ddev`` → ``stg`` → ``prod``, gated by canary + manual
       judgement (or auto-promote, depending on archetype). See
       :ref:`infra-overview` § *Spinnaker pipelines*.

   SLAuth
       Atlassian's internal session/auth proxy. Inbound JWT
       validation happens at the **edge proxy** *before* the
       request reaches this service; the proxy attaches a fixed
       set of ``X-Slauth-*`` headers
       (``X-Slauth-User-Context-Status``,
       ``X-Slauth-User-Context``,
       ``X-Slauth-User-Context-Account-Id``,
       ``X-Slauth-User-Context-Request-Principal``,
       ``X-Slauth-Issuer``, ``X-Slauth-Principal``).
       ``src/slauth/user_context.py`` is therefore a header
       *parser*, not an authenticator — the service never
       validates JWTs in-process for inbound traffic. (Outbound
       *ASAP* JWT signing is a separate concern, performed via
       ``config.asap_signer`` in the antiabuse and Triton-gRPC
       outbound paths.) See :ref:`config-overview`
       § *Auth context (slauth)*.

   Statsig
       The feature-flag platform that gates 25 of the 26 strings
       in the project's ``Features`` enum (the 26th —
       ``ENABLE_RESPONSE_HANDLING`` — is unused; recorded as a
       documented ambiguity). Backed by
       ``atlassian_feature_gate.FeatureGateClient`` with
       ``local_mode=config.is_local`` and a per-env
       ``StatsigEnvironmentTier``. Gate evaluation is
       per-(tenant, user) — ``tenantId=cloud_id``,
       ``atlassianAccountId=user_id``; a missing tenant ID
       short-circuits to ``False`` *without* calling Statsig.
       Three layered override mechanisms exist:
       ``feature_flag_overrides.json`` (file, applied at
       ``FeatureService.__init__`` in local mode),
       ``/v1/admin/feature-flag/<user>/<flag>/{enable,disable,reset}``
       (in-process admin endpoints, ``@only_locally``-gated), and
       ``set_request_overrides()`` on Flask ``g`` (per-request
       debug). See :ref:`config-overview`
       § *Feature gating: Statsig*.

   tenant context
       The ``cloud_id → org_id → settings`` lookup chain owned by
       ``TenantContextClient`` (``src/tenant_context/tenant_context_client.py``),
       which calls the **Tenant Context Service (TCS)** sidecar
       at ``config.tcs_url``
       (``http://{TCS_SIDECAR_HOST}:{TCS_SIDECAR_HTTP_PORT}``,
       default ``http://localhost:50050``). Three methods
       (``get_organisation_id_from_cloud_id``,
       ``get_organisation_control_for_hosted_llms``,
       ``get_hosted_llms_settings_for_cloud_id``) all use
       ``requests.get(timeout=0.6)`` — **no retries, no circuit
       breaker, no Session reuse**. The current sole consumer is
       the agent moderation service's external-LLM-blocking
       decision, gated by
       ``is_read_external_llm_calls_org_setting_enabled``. The
       inbound tenant ID itself flows through requests as
       ``X-Atlassian-CloudId`` and is bundled into
       ``ModerationRequestContext``. See :ref:`config-overview`
       § *Tenant context (TCS)*.

   Triton
       NVIDIA's Triton Inference Server. The service runs **two
       distinct Triton clients in parallel**:
       ``src/inference_models/triton_grpc_client.py``
       (``GrpcEndpoint`` over ``tritonclient.grpc``,
       ``timeout=5_000_000`` µs server-side, ``client_timeout=6 s``,
       used by Llama Teamserve variants for the named model
       ``teamserve-rai-optimized-logits``) and
       ``src/inference_models/triton_openai_api_client.py``
       (``TritonOpenAIClient`` over the Triton-served
       OpenAI-compatible HTTP path ``/v1/chat/completions``,
       ``timeout=6 s``, used by GPT-OSS Safeguard 20b). Both wrap
       calls in a
       ``pybreaker.CircuitBreaker(name="triton_circuit_breaker", fail_max=30)``;
       the breakers share the *name* (for telemetry) but each
       instance has independent state. The two transports
       coexist because their score-derivation requirements
       differ — gRPC returns per-token ``log_probs`` (so the
       violation score is ``softmax(log_probs[5])[0]``), the
       OpenAI HTTP path does not (so the GPT-OSS score is
       binary). Triton gRPC also requires
       ``grpc.experimental.gevent.init_gevent()`` at boot, before
       the first client is constructed, or every gRPC call
       serializes through the gRPC threadpool instead of
       cooperating with gevent. See :ref:`inf-models`
       § *Wire-protocol clients* and § *Why two Triton client
       variants exist*.

.. _anchor-map:

Shared Anchor Map
=================

The registry below lists every named ``.. _<name>:`` cross-reference
target that any of the eight documentation pages defines or is
expected to define, grouped by page. Each row is

.. parsed-literal::

   ``anchor-name`` → *file.rst:line* → *one-line purpose*

This is the deliverable the project requested as the "shared anchor
map" — a single registry that makes the cross-reference graph
machine-discoverable. :term:`nitpicky mode` cross-checks every
``:ref:`` against this set.

How to read this table
----------------------

* **Defined.** A row tagged *"defined — file.rst:line"* corresponds
  to an actual ``.. _<anchor>:`` directive that exists in the named
  source file at the named line. ``:ref:`anchor``` resolves under
  ``nitpicky`` today.
* **Forward-referenced (planned).** A row tagged *"forward-referenced
  — target page not yet authored"* names an anchor that is *cited*
  from one or more existing pages but whose containing page has not
  yet been authored. Listed here so the registry remains a single
  source of truth across the build-out: when the page lands, the
  anchor name and rough purpose should match what existing pages
  already assume. Until then ``:ref:`anchor``` will fail under
  ``nitpicky``.

Counts at the time this glossary was written
--------------------------------------------

Confirmed by ``grep -n '^\.\.\s_[A-Za-z][A-Za-z0-9_-]*:' docs/source/*.rst``:

* **4 defined anchors** across 3 existing files
  (``operations.rst`` × 2, ``inference-models.rst`` × 1,
  ``configuration.rst`` × 1).
* **2 new anchors** introduced by *this* glossary page
  (``glossary``, ``anchor-map``).
* **9 forward-referenced anchors** in 5 not-yet-authored pages
  (``introduction``, ``getting-started`` + ``gs-feature-flags``,
  ``architecture`` + ``arch-debug-trace``, ``service-layer`` →
  ``svc-moderation``, ``api-reference`` + ``api-etag`` +
  ``api-debug-trace``).

introduction.rst
----------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``introduction``
     - forward-referenced — target page not yet authored
     - Page-top anchor for the project introduction. Cited by
       ``configuration.rst:10, 2052, 2112`` to forward-reference
       service purpose / scope.

getting-started.rst
-------------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``getting-started``
     - forward-referenced — target page not yet authored
     - Page-top anchor for local toolchain, run modes, ``flask
       run`` vs ``gunicorn`` boot caveats, and the
       ``feature_flag_overrides.json`` workflow. Cited 10× across
       ``operations.rst`` and ``configuration.rst``.
   * - ``gs-feature-flags``
     - forward-referenced — target page not yet authored
     - Sub-anchor on ``getting-started`` covering the
       developer-laptop counterpart of ``Local overrides`` /
       admin endpoints. Cited from ``configuration.rst:2055``.

architecture.rst
----------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``architecture``
     - forward-referenced — target page not yet authored
     - Page-top anchor for the request lifecycle, blueprint tree,
       FlaskMicros wiring, and the global error-handler chain.
       Cited 17× — the most-referenced anchor in the
       documentation; the largest forward-reference debt.
   * - ``arch-debug-trace``
     - forward-referenced — target page not yet authored
     - Sub-anchor on ``architecture`` covering how the
       ``debug_trace`` (see :term:`debug trace`) propagates through
       the global handler chain (``InternalServerError`` /
       ``APIException`` paths). Required by the glossary's
       *debug trace* entry.

service-layer.rst
-----------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``svc-moderation``
     - forward-referenced — target page not yet authored
     - Page-top anchor for the four moderation services
       (``PromptModerationService``,
       ``ImageModerationService``,
       ``AgentModerationService``, ``OutputModerationService``)
       that consume the inference layer and the configuration
       layer. Cited 9× from ``inference-models.rst`` and
       ``configuration.rst``.

inference-models.rst
--------------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``inf-models``
     - **defined — inference-models.rst:1**
     - Page-top anchor for the ``src/inference_models/`` package:
       model abstractions, the three Llama variants + GPT-OSS,
       SageMaker image clients, both Triton transports,
       confidence subpackage, model-shadowing subpackage, and
       the fail-open / circuit-breaker policy. **The most-cited
       anchor on the existing pages (37×).**

configuration.rst
-----------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``config-overview``
     - **defined — configuration.rst:1**
     - Page-top anchor for Layer 4 (cross-cutting platform
       modules): ``src/config.py``, ``feature_service.py``,
       Statsig + dynamic config, ``slauth/`` and
       ``tenant_context/``, ``cache/time_cache.py``,
       ``exception.py``, ``gasv3_analytics/``, ``metrics/``,
       ``ml_platform/``, ``antiabuse/``. Cited 10× across the
       other existing pages.

api-reference.rst
-----------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``api-reference``
     - forward-referenced — target page not yet authored
     - Page-top anchor for the public HTTP contract: the four
       moderation endpoints, the admin feature-flag endpoints,
       analytics emission, latency metric, required headers,
       tenant context construction. Cited 13×.
   * - ``api-etag``
     - forward-referenced — target page not yet authored
     - Sub-anchor on ``api-reference`` for the prompt-cache
       :term:`ETag` protocol — what is hashed, the weak-ETag
       form, the ``If-None-Match`` short-circuit, the
       prompt-only scope. Cited from ``configuration.rst:1070,
       2066``.
   * - ``api-debug-trace``
     - forward-referenced — target page not yet authored
     - Sub-anchor on ``api-reference`` for the response shape of
       the :term:`debug trace` — what the ``"trace"`` key
       contains when ``debug.verbose=true`` is set on the
       request. Required by the glossary's *debug trace* entry.

operations.rst
--------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``infra-overview``
     - **defined — operations.rst:1**
     - Page-top anchor for the *deployment surface* portion of
       this combined page: Atlassian :term:`Micros` descriptors,
       container build, Helm charts, :term:`Spinnaker` pipelines,
       CI/build, runtime (gunicorn + gevent + gRPC patching),
       quality gates (pre-commit, pyright, coverage floors,
       Sonar, Sauron). External pages should target this anchor
       only when they want the build/runtime/quality material —
       not the runbooks below.
   * - ``ops-overview``
     - **defined — operations.rst:591**
     - Mid-page anchor for the *operational runbooks* portion:
       HTTP pool exhaustion, gRPC circuit-breaker recovery,
       :term:`AI Gateway` upstream incidents, monitoring &
       alerting hooks, operational ambiguities. **External
       links to the operational portion should target
       ``ops-overview`` directly to avoid landing readers on
       the build-system material** (call-out from
       ``operations.rst:24-33``).

glossary.rst (this page)
------------------------

.. list-table::
   :header-rows: 1
   :widths: 24 30 46

   * - Anchor
     - Where defined
     - Purpose
   * - ``glossary``
     - **defined — glossary.rst:1**
     - Page-top anchor. Use ``:ref:`glossary``` when linking the
       page itself; use ``:term:`<name>``` when linking an
       individual term inside the ``.. glossary::`` directive.
   * - ``anchor-map``
     - **defined — glossary.rst** (above this section)
     - Anchor for the registry on this page (the table set you
       are reading). Use ``:ref:`anchor-map``` to direct readers
       to the cross-reference index rather than the term list.

Cross-references
================

The glossary deliberately backward-links to **all eight** of the
documentation pages listed in the :ref:`anchor-map`. It does **not**
modify those pages. Each link below has at least one ``:ref:`` /
``:term:`` consumer in the glossary entries above:

* :ref:`introduction` — :term:`RAI` (project name and scope).
* :ref:`getting-started` — local toolchain referenced from
  :term:`Statsig` (file overrides), :term:`pool timeout`
  (developer caveat). Sub-anchor :ref:`gs-feature-flags` for the
  developer-laptop counterpart of admin endpoints.
* :ref:`architecture` — request lifecycle and global handler chain
  referenced from :term:`debug trace` (sub-anchor
  :ref:`arch-debug-trace`), :term:`Micros` (FlaskMicros wiring),
  :term:`ETag` (cache mechanism placement).
* :ref:`svc-moderation` — orchestration layer referenced from
  :term:`harm category`, :term:`shadow model` (selector site),
  :term:`tenant context` (agent-moderation consumer).
* :ref:`inf-models` — *defined*. Cited from :term:`AI Gateway`,
  :term:`confidence threshold`, :term:`harm category`,
  :term:`shadow model`, :term:`Triton`.
* :ref:`config-overview` — *defined*. Cited from :term:`AI Gateway`
  (retry config), :term:`GAS v3`, :term:`Micros` (StatsD wiring),
  :term:`Nebulae` (env var), :term:`policy filter` (event schema),
  :term:`SLAuth`, :term:`Statsig`, :term:`tenant context`.
* :ref:`api-reference` — public HTTP contract referenced from
  :term:`debug trace` (sub-anchor :ref:`api-debug-trace`),
  :term:`ETag` (sub-anchor :ref:`api-etag`).
* :ref:`infra-overview` and :ref:`ops-overview` — *defined*. Cited
  from :term:`Micros`, :term:`Nebulae`, :term:`Spinnaker`,
  :term:`pool timeout`.

Documented ambiguities
======================

Items surfaced while authoring this page. They mirror the
``Documented ambiguities`` blocks in :ref:`config-overview` and
:ref:`infra-overview` so each page stands on its own.

#. **Five forward-referenced pages.** ``introduction``,
   ``getting-started``, ``architecture``, ``service-layer``, and
   ``api-reference`` are cited by anchor name from the existing
   .rst files but have not yet been authored. Until they land,
   ``:ref:`api-etag``` (and 8 others — see :ref:`anchor-map`)
   fail under :term:`nitpicky mode`. The glossary's
   :term:`debug trace` and :term:`ETag` entries are written
   against the assumption that ``api-debug-trace``,
   ``api-etag``, and ``arch-debug-trace`` will land as
   sub-anchors on those pages with the purposes described in the
   anchor map.

#. **Term ``debug trace`` is defined here but the source-of-truth
   page does not exist yet.** The definition above is anchored
   to the existing ``DebugTrace``-related material in
   :ref:`config-overview` § *Exception model* (1175–1181) and
   the global handler chain summary at lines 1183–1208. When
   ``architecture.rst`` and ``api-reference.rst`` land, this
   entry should be tightened to point at their canonical
   sections (``arch-debug-trace`` and ``api-debug-trace``)
   rather than at the configuration page's pass-through
   description.

#. **Build harness verified at glossary author time.** ``conf.py``
   exists and sets ``nitpicky = True`` (``docs/source/conf.py:52``);
   ``index.rst`` exists with the 8-page toctree
   (``docs/source/index.rst:22-34``) listing
   ``introduction``, ``getting-started``, ``architecture``,
   ``service-layer``, ``inference-models``, ``configuration``,
   ``api-reference``, ``operations``, ``glossary``. ``Makefile`` is
   not checked in — the build is expected to be driven directly by
   ``sphinx-build`` (the ``nitpicky = True`` setting in ``conf.py``
   makes the ``-n`` flag redundant). The anchor map below is
   therefore the live registry the build cross-checks against, and
   the 9 forward-referenced rows below are exactly what the build
   subtask should report as unresolved until the 5 missing pages
   land.

#. **Term ``harm category`` cites both ``PromptHarmCategory`` and
   ``ImageHarmCategory``.** The original task brief cited
   ``AgentHarmCategory`` / ``ImageHarmCategory``, but the
   existing .rst sources consistently show
   ``PromptHarmCategory`` as the vocabulary used by the
   prompt + agent + output paths (see ``inference-models.rst:252``
   and ``configuration.rst:1314-1320``). If a separate
   ``AgentHarmCategory`` enum exists in ``schema/`` outside the
   .rst-documented surface, the entry should be updated when the
   service-layer page documents it.

#. **Term ``pool timeout`` describes "four 10 s timeouts" without
   verifying their exact identities.** The current
   ``operations.rst`` runbook (lines 615–706) names only the 5 s
   ``pool_timeout``. The four 10 s siblings on
   ``default_http_config`` (presumably some combination of
   ``connect`` / ``read`` / ``write`` and an overall timeout)
   are referenced from the project task brief but not documented
   in the existing .rst files. When ``app_context.py:47`` is
   documented in :ref:`architecture` or :ref:`api-reference`,
   tighten this entry to cite the four exact field names.

Verification anchors
====================

The following claims were verified against the three existing .rst
files. Each entry points to the file and line range so a reader can
re-check by hand.

* **4 ``.. _<anchor>:`` definitions** across 3 files, found by
  ``grep -nE '^\.\. _[A-Za-z][A-Za-z0-9_-]*:'`` over
  ``docs/source/*.rst``: ``_config-overview:`` at
  ``configuration.rst:1``, ``_inf-models:`` at
  ``inference-models.rst:1``, ``_infra-overview:`` at
  ``operations.rst:1``, ``_ops-overview:`` at
  ``operations.rst:591``.
* **9 unique ``:ref:`` targets** across 3 files, found by
  ``grep -roh ':ref:\`[^\`]*\`' docs/source/ | sort -u``: the four
  defined anchors above plus the five forward-referenced page-top
  anchors (``introduction``, ``getting-started``, ``architecture``,
  ``svc-moderation``, ``api-reference``) and two forward-referenced
  sub-anchors (``api-etag``, ``gs-feature-flags``). Two further
  sub-anchors (``arch-debug-trace``, ``api-debug-trace``) are
  reserved by the glossary's ``debug trace`` entry but are not
  *yet* cited from any other page.
* :term:`AI Gateway` retry config —
  ``configuration.rst:1711-1717`` and
  ``operations.rst:805-813`` agree on tenacity 2 attempts,
  ``wait_random_exponential(0.5–1.5s)``, retrying only
  ``httpx.TimeoutException`` / ``httpx.NetworkError``, gated by
  ``is_custom_retry_config_enabled``.
* :term:`confidence threshold` —
  ``inference-models.rst:791-829``,
  ``configuration.rst:721-737``: per-tenant via
  ``Identifiers(tenantId=...)``, cached for 60 s,
  ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5``, comparison is
  ``score >= threshold``.
* :term:`debug trace` —
  ``configuration.rst:1175-1181`` and
  ``configuration.rst:1183-1208`` (global handler chain summary
  pointing at :ref:`architecture`).
* :term:`ETag` — ``configuration.rst:1051-1072`` (Connection to
  the ETag mechanism), ``configuration.rst:2066`` (sub-anchor
  cite).
* :term:`GAS v3` — ``configuration.rst:1210-1407`` plus
  fire-points at lines 2284-2292.
* :term:`harm category` —
  ``inference-models.rst:251-252`` (``PromptHarmCategory.NONE``
  in fail-open path), ``configuration.rst:1314-1320``
  (``detectedHarmCategory`` event field),
  ``configuration.rst:1860-1867`` (``ImageHarmCategory`` mapping
  table).
* :term:`Micros` — ``operations.rst:88-147`` (Atlassian Micros
  conventions), ``configuration.rst:1442-1453`` (FlaskMicros
  wiring).
* :term:`Nebulae` — ``operations.rst:101-105``,
  ``configuration.rst:239-246`` (``NEBULAE`` env var,
  ``is_local`` derivation), ``configuration.rst:262-270``
  (``MESH_DEPENDENCY_AI_GATEWAY_BASE_URL`` composition).
* :term:`pool timeout` — ``operations.rst:615-624``
  (``default_http_config`` at ``app_context.py:47``,
  ``pool_timeout=5 s``).
* :term:`policy filter` — ``configuration.rst:1213-1231``
  (subpackage layout), ``configuration.rst:1332-1336``
  (``ContentEvaluatedEvent`` action_subject pair).
* :term:`RAI` — ``configuration.rst:175-177``
  (``app_name = "responsible-ai-api"``),
  ``configuration.rst:182-186`` (logger),
  ``configuration.rst:706-707``
  (``namespace="responsible-ai-api_server"``),
  ``inference-models.rst:1188-1190`` (Triton model name).
* :term:`shadow model` — ``inference-models.rst:850-911``
  (Model shadowing section).
* :term:`Spinnaker` — ``operations.rst:202-234``.
* :term:`SLAuth` — ``configuration.rst:753-817``.
* :term:`Statsig` — ``configuration.rst:378-456`` (the
  facade), ``configuration.rst:457-562`` (gate inventory).
* :term:`tenant context` — ``configuration.rst:819-878``.
* :term:`Triton` — ``inference-models.rst:684-739`` (both
  client files), ``inference-models.rst:1017-1047``
  (Why two variants exist),
  ``operations.rst:282-358`` (gRPC + gevent boot order).
