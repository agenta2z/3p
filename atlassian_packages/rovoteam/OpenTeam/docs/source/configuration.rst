.. _config-overview:

==========================================
Configuration & cross-cutting concerns
==========================================

.. note::

   This page resolves the ``config-overview`` anchor that the four
   foundation pages (:ref:`introduction`, :ref:`getting-started`,
   :ref:`architecture`, :ref:`api-reference`) and the two layer pages
   (:ref:`svc-moderation`, :ref:`inf-models`) forward-reference. It
   documents Layer 4 of the layering map in :ref:`architecture` —
   *cross-cutting platform* modules that any other layer can import.

   Topics covered: static configuration (``src/config.py``); feature
   gating (``feature_service.py``, ``statsig_flags/``, ``dynamic_config/``);
   auth and tenancy (``slauth/``, ``tenant_context/``); caching
   (``cache/time_cache.py``); the exception model (``exception.py``);
   analytics emission (``gasv3_analytics/``); StatsD metrics
   (``metrics/``); ML-platform integration (``ml_platform/``); and
   anti-abuse integration (``antiabuse/``).

   The page does **not** re-document material that is the ground truth
   somewhere else: the global error-handler chain lives in
   :ref:`architecture` § *Error and exception handling*; the ETag
   protocol lives in :ref:`api-reference` § *ETag handling*; the
   admin feature-flag endpoints are documented in :ref:`api-reference`
   § *Admin*. Forward-pointers below cite those exact sections.

.. contents::
   :local:
   :depth: 2

Purpose & scope
===============

The ``src/`` modules covered here have one common property: they are
*usable from any layer above them*. ``config.config`` is imported from
controllers, services, inference clients, and from one another;
``feature_service`` is consulted from controllers (analytics gate),
services (model selection, fail-open policy), and inference clients
(retry config, tokenization strictness); ``send_metric`` and
``RAIAnalyticsClient`` fan out from controllers to operations
dashboards. Treating them as a single horizontal slice — rather than
sprinkling them through the per-layer pages — is what makes the
contract between layers legible.

Three orthogonal axes organise the page:

#. **What carries information through a request** — auth context,
   tenant context, the request-scoped feature-flag overrides, and the
   ``ModerationRequestContext`` that bundles them. These flow
   *explicitly* (parameter passing) rather than via Flask's ``g``
   object or contextvars.
#. **What controls behaviour at runtime** — Statsig gates (binary,
   per-tenant), dynamic config (per-tenant JSON/list, 60-second
   cached), local overrides (``feature_flag_overrides.json`` plus
   ``/v1/admin/feature-flag/...`` mutators in local mode only), and
   static config (``os.environ`` evaluated once at process boot).
#. **What flows out** — analytics events to GASv3, StatsD metrics
   wired through ``FlaskMicros(app)``, structured logs to the Micros
   log pipeline, OpenTelemetry traces to OTLP/HTTP. Each has a
   specific failure mode.

The page is intended to be read end-to-end once and then dipped into
by reference. Every claim below is anchored to a file path and (where
useful) a line number so the reader can verify by hand. Ambiguities
that surfaced during authoring are recorded in
`Documented ambiguities`_ at the end.

Module-to-topic map
===================

.. list-table:: Layer 4 modules and the section that documents each
   :header-rows: 1
   :widths: 36 18 46

   * - Module
     - Topic
     - Notes
   * - ``src/config.py``
     - `Static configuration`_
     - Singleton ``Config`` instantiated at import; reads ~20 env
       vars; validates ASAP credentials in non-local mode.
   * - ``src/feature_service.py``
     - `Feature gating: Statsig`_
     - 26 ``Features`` enum members, 25 ``is_*``/``should_*`` methods,
       per-request override hook on Flask ``g``.
   * - ``src/statsig_flags/local_overrides.py``
     - `Local overrides`_
     - Loads ``feature_flag_overrides.json`` once per process when
       ``config.is_local`` is true.
   * - ``src/dynamic_config/client.py``
     - `Dynamic config (per-tenant)`_
     - Wraps ``StatsigSidecarClient`` under the
       ``responsible-ai-api_server`` namespace; one cached singleton.
   * - ``src/slauth/user_context.py``
     - `Auth context (slauth)`_
     - Parses six ``X-Slauth-*`` headers into
       ``SlauthUserContextHeaders``; never validates JWTs in process.
   * - ``src/tenant_context/tenant_context_client.py``
     - `Tenant context (TCS)`_
     - ``cloud_id → org_id → settings`` HTTP chain via the TCS
       sidecar; 600 ms timeout per call; no retries.
   * - ``src/cache/time_cache.py``
     - `Caching: time_cache`_
     - 27-line LRU+time-salt decorator; only used by the per-tenant
       confidence-threshold lookups.
   * - ``src/exception.py``
     - `Exception model`_
     - ``APIException`` + ``make_api_error_response``; the global
       handler chain is in :ref:`architecture`.
   * - ``src/gasv3_analytics/``
     - `Analytics: GASv3`_
     - Four event types fanned out via a ``gevent.pool.Pool(10)``;
       failures are swallowed and logged.
   * - ``src/metrics/``
     - `Metrics: StatsD via FlaskMicros`_
     - ``send_metric`` + ``measure_latency`` decorators; everything
       routes through ``g.global_stat`` populated by FlaskMicros.
   * - ``src/ml_platform/``
     - `ML platform: input moderation client`_
     - Wraps the AI Gateway SDK for the legacy ``V2_3_3_prompt_v2``
       Llama path; ``UseCases`` enum is referenced by
       ``feature_service.is_use_case_allowed()``.
   * - ``src/antiabuse/``
     - `Anti-abuse integration`_
     - HTTPX client with ASAP JWT auth and a circuit breaker; image
       moderation only.

The five modules under ``src/metrics/`` (plus ``src/gasv3_analytics/``)
are written *for* a specific layer (controllers and services emit;
the inference layer does not emit metrics or analytics directly). All
other modules listed above are genuinely usable from anywhere.

Static configuration
====================

``src/config.py`` is the project's *only* static-config singleton.
It is instantiated **once** at module import as
``config = Config()`` (``config.py:182``) and every other module that
needs settings imports the symbol ``config`` directly. There is no
context-manager, no reload primitive, no second instantiation site.

What's in the singleton
-----------------------

The constructor (``Config.__init__``, ``config.py:43-148``) reads
environment variables and computes a small set of derived attributes.
The full attribute list, grouped by purpose:

.. list-table:: ``config`` singleton attributes
   :header-rows: 1
   :widths: 32 32 36

   * - Attribute
     - Source
     - Notes / default
   * - ``service_url``
     - ``MICROS_SERVICE_DOMAIN_NAME``
     - Defaults to ``"http://localhost"`` (the ``LOCAL_HOST`` constant
       at ``config.py:30``).
   * - ``env_type``
     - ``MICROS_ENVTYPE``
     - Coerced through ``EnvType(...)``; unparseable values fall back
       to ``EnvType.LOCAL`` via ``EnvType._missing_``
       (``config.py:25-27``). Missing env var → ``EnvType.UNKNOWN``.
   * - ``micros_aws_region``
     - ``MICROS_AWS_REGION``
     - Defaults to the literal string ``"unknown"``. Used as the
       ``region`` tag on every metric (see `Metrics: StatsD via
       FlaskMicros`_ — ``DEFAULT_TAGS`` in
       ``metrics_handler.py:45``).
   * - ``app_name``
     - hard-coded
     - ``"responsible-ai-api"`` (``config.py:56``).
   * - ``port``
     - hard-coded
     - ``8080`` (``config.py:57``). Local launcher overrides via
       gunicorn flag, see :ref:`getting-started`.
   * - ``logger``
     - constructed
     - ``logging.getLogger("responsible-ai-api")`` at INFO level. The
       singleton is the one most modules import via
       ``config.logger`` rather than calling ``getLogger`` themselves.
   * - ``version``
     - ``parse_version_json()``
     - Reads ``build-output/git-version.json`` and
       ``build-output/release-version.json`` (``config.py:170-179``).
       **These files must exist at startup** — a missing
       ``build-output/`` directory is a hard-fail on import. They are
       produced by the build pipeline; the local launcher writes
       fixtures (see :ref:`getting-started`).
   * - ``sm_endpoint_image_moderation``
     - ``SM_ENDPOINT_IMAGE_MODERATION_V0_ENDPOINT_NAME``
     - Default ``"image-moderation-v0"``. Consumed by
       ``ImageModerationSageMaker`` (see :ref:`inf-models`).
   * - ``sm_endpoint_image_moderation_v1``
     - ``SM_ENDPOINT_IMAGE_MODERATION_V1_MODEL_ENDPOINT_NAME``
     - Default ``"image-moderation-v1-model"``. Missing config raises
       ``ValueError`` at app start when ``ImageModerationV1Client`` is
       constructed (see :ref:`inf-models`).
   * - ``image_moderation_v0_threshold``
     - ``IMAGE_MODERATION_V0_THRESHOLD``
     - Default ``"0.4"`` → coerced via ``float()``. Image V0 score
       threshold (see :ref:`inf-models`).
   * - ``image_moderation_v1_threshold``
     - ``IMAGE_MODERATION_V1_THRESHOLD``
     - Default ``"0.5"`` → ``float()``. Image V1 / ShieldGemma score
       threshold.
   * - ``antiabuse_api_base_url``
     - ``ANTIABUSE_API_BASE_URL``
     - Default depends on ``env_type`` via
       ``_get_default_antiabuse_url`` (``config.py:150-156``):
       ``DEV → abuse-filescanner.ap-southeast-2.dev.atl-paas.net``;
       ``STAGING → abuse-filescanner-stg-east.staging.atl-paas.net``;
       ``PROD → abuse-filescanner-prod-east.prod.atl-paas.net``;
       any other env type → ``DEV`` URL.
   * - ``sagemaker_inference_timeout``
     - ``SAGEMAKER_INFERENCE_TIMEOUT``
     - Default ``30`` (the ``DEFAULT_SAGEMAKER_INFERENCE_TIMEOUT``
       constant at ``config.py:33``).
   * - ``greenlet_join_timeout``
     - ``GREENLET_JOIN_TIMEOUT``
     - Default ``30`` (``DEFAULT_GREENLET_JOIN_TIMEOUT``). Used by
       parallel V0/V1 image inference (see :ref:`inf-models`).
   * - ``inference_pool_size``
     - ``INFERENCE_POOL_SIZE``
     - Default ``2`` (``DEFAULT_INFERENCE_POOL_SIZE``). Sizes the
       gevent pool used for parallel image V0/V1.
   * - ``statsig_sdk_key``
     - ``STATSIG_SERVER_SDK_KEY``
     - Default ``"secret-dummykey"`` — *intentional dev fallback*.
       The same key value is what ``feature_service`` would attempt
       to bootstrap with if no real Statsig key is plumbed in,
       so keep ``config.is_local`` true in that case (see
       `Feature gating: Statsig`_).
   * - ``is_nebulae``
     - ``NEBULAE`` (string ``"true"``)
     - Boolean, used in the ``is_local`` heuristic.
   * - ``is_local``
     - derived
     - ``EnvType(env_type) == EnvType.LOCAL or service_url == LOCAL_HOST or is_nebulae``
       (``config.py:96-100``). Three independent inputs collapse into
       one flag; any of the three flips the service into local mode.
   * - ``tcs_url``
     - ``TCS_SIDECAR_HOST`` + ``TCS_SIDECAR_HTTP_PORT``
     - Composed as ``f"http://{host}:{port}"``; defaults
       ``"localhost":"50050"``. ``TenantContextClient`` reads this
       once at construction (see `Tenant context (TCS)`_).
   * - ``asap_signer``
     - ``ASAP_ISSUER`` + ``ASAP_PRIVATE_KEY``
     - **Validated at startup** — see `Startup-time validation`_
       below. In local mode with ``NO_ASAP_SIGNER=true`` it is set to
       a ``unittest.mock.Mock(JWTAuthSigner)``.
   * - ``teamserve_endpoint``
     - ``TEAMSERVE_ENDPOINT``
     - Default
       ``"grpc-teamserve-us-west-2.dev.services.kitt-inf.net"`` — the
       *dev* endpoint. Production deploys override via env var.
   * - ``teamserve_gptoss_endpoint``
     - ``TEAMSERVE_GPTOSS_ENDPOINT`` (with conditional default)
     - Conditional default: if
       ``MESH_DEPENDENCY_AI_GATEWAY_BASE_URL`` is set, the default is
       ``f"{ai_gw_base}/gptoss-teamserve/v1/chat/completions"`` (the
       Nebulae integration-test wiring, ``config.py:128-140``);
       otherwise it falls back to a hard-coded staging URL on
       ``teamserve-us-west-2.stg.services.kitt-inf.net``.
       Production deploys override the env var directly.
   * - ``statsig_environment``
     - derived from ``env_type``
     - Maps ``EnvType.STAGING → StatsigEnvironmentTier.staging``,
       ``EnvType.PROD → StatsigEnvironmentTier.production``,
       *everything else* → ``StatsigEnvironmentTier.development``
       (``config.py:142-145``). This is what ``FeatureService`` hands
       to the Statsig client.
   * - ``git_version``, ``release_version``
     - parsed JSON
     - Whole files loaded as dicts; ``version`` is the
       ``release_version["version"]`` string. Surfaced by
       ``GET /health-check`` (see :ref:`api-reference`).

The full list of *environment variables* read by ``Config.__init__``
is exactly the union of the **Source** column above plus
``NO_ASAP_SIGNER`` and ``NO_CHECK_REQUIRED_VARS`` (skip-flags, not
stored on ``config``). There are no other ``os.environ`` /
``os.getenv`` calls in the file.

Override precedence
-------------------

The precedence story is short because the file is small:

#. **Environment variable** (when set) wins for every attribute that
   has an env-var source.
#. **Hard-coded default** in the call to ``os.environ.get(name,
   default)`` is the only fallback.

There is **no file-based config**, no YAML loader, no merging of
multiple sources. Dynamic config (covered separately, see
`Dynamic config (per-tenant)`_) is a *different* mechanism whose
results are not stored on the ``config`` singleton — they are
fetched lazily, per-tenant, with their own caching layer. So the
question "env vs file vs dynamic config" decomposes into:

* **Static config** (``config.py``) — env or hard-coded default,
  evaluated **once** at process boot, frozen for the process lifetime.
* **Dynamic config** (``dynamic_config/client.py``) — fetched from
  the Statsig sidecar per call, per-tenant, cached for 60 seconds via
  ``time_cache``. Used only by the prompt confidence-threshold
  lookups today.
* **Feature flags** (``feature_service.py``) — Statsig gates
  evaluated per call against a per-tenant + per-user identifier;
  local overrides apply on top in local mode.

These three layers do not override each other — they describe
different things. Static config holds infrastructure addresses and
tunables; dynamic config holds tenant-scoped numerics; feature flags
hold boolean policy.

Startup-time vs runtime mutability
----------------------------------

Static config is **frozen at startup**. The ``Config`` constructor
runs once; the singleton's attributes are not re-read from
environment after that point. To change a static-config value the
process must be restarted.

Two settings have *startup-time validation*:

* **ASAP signer** (``config.py:107-123``). When
  ``config.is_local and os.environ.get("NO_ASAP_SIGNER") == "true"``,
  ``self.asap_signer`` is a ``Mock(JWTAuthSigner)`` and validation is
  skipped. Otherwise the constructor reads ``ASAP_ISSUER`` and
  ``ASAP_PRIVATE_KEY`` and **raises** ``ValueError`` if either is
  missing or empty. So in *any* non-local deploy without
  ``NO_ASAP_SIGNER=true`` the process fails to import without a real
  ASAP keypair. The signer is then constructed with
  ``atlassian_jwt_auth.create_signer(issuer, key_id, pem,
  reuse_jwts=True)`` — JWTs are reused between calls.
* **Required-vars guard** (``config.py:147-148``). If
  ``NO_CHECK_REQUIRED_VARS`` is unset, ``check_required_vars_are_set()``
  iterates ``self._required_vars`` and raises ``ValueError`` listing
  any missing names. **Today the list is empty** (``self._required_vars =
  []`` at ``config.py:91``) — so the check is a no-op until something
  populates the list. Recorded in `Documented ambiguities`_ below.

Several settings have *startup-time read-once* semantics that are not
quite "validation" but are still load-bearing:

* **Version files** (``parse_version_json``, ``config.py:170-179``).
  Both ``build-output/git-version.json`` and
  ``build-output/release-version.json`` are opened and parsed at
  import. A missing or malformed file is a startup failure. The
  fixture for local development is written by the launcher (see
  :ref:`getting-started`).
* **Antiabuse base URL fallback** (``_get_default_antiabuse_url``,
  ``config.py:150-156``). The fallback is read from a hard-coded dict
  keyed on ``env_type``; an unrecognised env type silently falls back
  to the ``DEV`` URL. A non-prod URL leaking into a prod deploy
  through this branch would not be flagged.

Connection to the inference layer
---------------------------------

Several ``config`` attributes are referenced from
:ref:`inf-models` — the cross-page contract is just "this attribute
exists at runtime." For convenience the inference-layer-relevant
attributes are: ``image_moderation_v0_threshold``,
``image_moderation_v1_threshold``, ``inference_pool_size``,
``greenlet_join_timeout``, ``sm_endpoint_image_moderation``,
``sm_endpoint_image_moderation_v1``, ``teamserve_endpoint``,
``teamserve_gptoss_endpoint``, and ``asap_signer``. The
inference page documents what *uses* each; this page documents what
*sets* each.

Feature gating: Statsig
=======================

``src/feature_service.py`` is the single facade in front of three
backing mechanisms:

#. **Statsig** (via ``atlassian_feature_gate.FeatureGateClient``) —
   the source of truth in real environments.
#. **Local overrides file** (``feature_flag_overrides.json`` at the
   repo root) — applied at construction when ``config.is_local`` is
   true, see `Local overrides`_.
#. **Per-request debug overrides** stored on Flask's ``g`` —
   ``set_request_overrides()`` / ``get_request_overrides()``
   (``feature_service.py:113-130``). When set, they short-circuit the
   Statsig check entirely.

The complete public surface — every public method, every gate name —
is described below. The ``feature_service`` singleton is constructed
at import (``feature_service.py:256``) so any import that loads this
module triggers initialization of the Statsig SDK.

Initialization
--------------

``FeatureService.__init__`` (``feature_service.py:65-92``):

* Asserts ``config.statsig_sdk_key`` is non-None and constructs a
  ``FeatureGateClient`` with:

  * ``sdk_key`` — from ``config.statsig_sdk_key`` (env
    ``STATSIG_SERVER_SDK_KEY``; dev fallback ``"secret-dummykey"``).
  * ``environment_type`` — ``config.statsig_environment``
    (development / staging / production, see `Static configuration`_).
  * ``options=FeatureGateClientOptions(local_mode=config.is_local,
    enable_debug_logs=...)``. ``local_mode`` is the SDK-level switch
    that prevents network calls to Statsig in dev. Debug logs are on
    in development and staging tiers.
* If ``config.is_local``, calls ``load_overrides_file()`` and applies
  every entry via ``self.override_flag_for_user(user, key, value)``.

The Statsig SDK initialization is synchronous (the
``atlassian_feature_gate`` package may perform a network bootstrap
of gate definitions at construction depending on
``local_mode``). Failure of that bootstrap surfaces as an exception
out of ``FeatureService()``; the ``app.py`` import would then fail.

Per-call user / tenant context
------------------------------

Every gate call funnels through ``_check_gate(gate_name)``
(``feature_service.py:132-156``) which:

#. Reads per-request debug overrides from Flask ``g`` and short-
   circuits if the gate is in the dict (returning the dict's bool).
#. Otherwise pulls the *current request's* tenant + user identifiers
   via ``ModerationRequestContext.from_incoming_http_request()`` and
   maps them to ``FeatureGateUserAttributes(tenantId=cloud_id,
   atlassianAccountId=user_id)``.
#. If ``tenantId`` is ``None`` or ``""``, **the gate defaults to
   False without calling Statsig**. This is the
   "no tenant header → all features off" behaviour and it is silent
   (one ``log.info`` per call). It matters for in-process unit tests
   that exercise gate-checking outside a request context.
#. Calls ``self._client.check_gate(feature_gate_user, gate_name)``.
   ``ValueError`` / ``TypeError`` / ``AttributeError`` /
   ``RuntimeError`` from the SDK are caught, logged, and resolved to
   ``False``.

There is **one gate** that does not go through ``_check_gate``:
``is_use_case_allowed()`` (``feature_service.py:237-241``) is *not*
backed by Statsig. It returns ``True`` if
``is_enabled_for_developer()`` is on, otherwise checks
``context.use_case_id in USE_CASE_IDS`` where
``USE_CASE_IDS = ["ai-policy-filtering"]`` (``feature_service.py:23``).
Tracking it as a "feature flag" alongside the Statsig-backed methods
is correct from the consumer's perspective but the underlying
mechanism is a hard-coded allow-list, not a dynamically-evaluable
gate.

Statsig gate inventory
----------------------

The ``Features`` enum (``feature_service.py:26-61``) declares **26
gate strings**. Twenty-five have a public method on
``FeatureService``; one (``ENABLE_RESPONSE_HANDLING``) has no caller
anywhere in the codebase — recorded in `Documented ambiguities`_.

.. list-table:: Statsig gates (gate string ↔ public method)
   :header-rows: 1
   :widths: 50 30 20

   * - Gate string
     - ``FeatureService`` method
     - Where consumed
   * - ``responsible_ai_agent_moderation_prompt_v_2_3_1``
     - ``is_agent_moderation_v2_3_1_enabled``
     - agent service
   * - ``responsible_ai_agent_moderation_v3``
     - ``is_agent_moderation_v3_enabled``
     - agent service
   * - ``rai_increased_input_clipping_buffer``
     - ``is_increased_input_clipping_buffer_enabled``
     - inference (token-budget buffer)
   * - ``rai_api_enable_user_input_logging``
     - ``is_user_input_logging_enabled``
     - logging policy
   * - ``rai_api_enable_connection_pool_logging``
     - ``is_connection_pool_logging_enabled``
     - healthcheck instrumentation
   * - ``rai_api_enable_extra_image_preprocessing``
     - ``is_extra_image_preprocessing_enabled``
     - image service
   * - ``rai_api_enable_image_moderation_v1``
     - ``is_image_moderation_v1_enabled``
     - image inference (V1 enable)
   * - ``rai_api_enable_image_moderation_antiabuse``
     - ``is_image_moderation_antiabuse_enabled``
     - image controller (antiabuse precheck)
   * - ``rai_api_disable_analytics``
     - ``is_analytics_disabled``
     - controllers (suppresses GASv3 emission)
   * - ``rai_enable_teamserve_shadowing``
     - ``is_rai_ft_teamserve_shadowing_enabled``
     - inference (shadow shim)
   * - ``rai_enable_teamserve_primary``
     - ``is_rai_ft_teamserve_primary_enabled``
     - inference (V2_3_3 teamserve as primary)
   * - ``rai_api_enable_response_handling``
     - **(unused — no method)**
     - **dead** — see `Documented ambiguities`_
   * - ``rai_api_should_fail_open_when_model_timesout``
     - ``should_fail_open_on_model_timeout``
     - inference (``inference_error_handler``)
   * - ``rai_api_enable_strict_tokenization_failure``
     - ``is_strict_tokenization_failure_enabled``
     - inference (tokenization assertion)
   * - ``rai_api_enable_custom_retry_config``
     - ``is_custom_retry_config_enabled``
     - app context (AI Gateway tenacity config)
   * - ``rai_api_enable_fail_open_on_circuit_breaker_open``
     - ``should_fail_open_if_circuit_breaker_open``
     - inference (``inference_error_handler``)
   * - ``rai_api_enable_safe_parse_json_response``
     - ``is_safe_parse_json_response_enabled``
     - inference (GPT-OSS JSON parse normalization)
   * - ``rai_enable_shadow_with_ai_gateway_2_3_3``
     - ``is_shadow_with_ai_gateway_2_3_3_enabled``
     - inference (shadow with AI-Gateway 2_3_3)
   * - ``rai_api_enable_teamserve_v2_4_primary``
     - ``is_prompt_moderation_teamserve_v2_4_primary_enabled``
     - inference (V2_4 as primary)
   * - ``rai_enable_shadow_with_teamserve_2_4``
     - ``is_shadow_with_teamserve_v2_4_enabled``
     - inference (shadow with V2_4)
   * - ``rai_enable_json_dynamic_config_thresholds``
     - ``is_json_dynamic_config_for_thresholds_enabled``
     - inference (per-version threshold lookup)
   * - ``rai_api_enable_standardized_image_api_response``
     - ``is_standardized_image_moderation_response_enabled``
     - image inference (response shape)
   * - (no gate — hard-coded allow-list)
     - ``is_use_case_allowed``
     - controllers + image preprocessing
   * - ``ai-gateway-block-external-llm-calls``
     - ``is_external_llm_calls_disabled``
     - agent service
   * - ``rai_api_read_external_llm_calls_org_setting``
     - ``is_read_external_llm_calls_org_setting_enabled``
     - agent service (TCS lookup gate)
   * - ``rai_api_enable_for_developer``
     - ``is_enabled_for_developer``
     - bypass for ``is_use_case_allowed``
   * - ``rai_api_enable_gptoss_safeguard``
     - ``is_gpt_oss_safeguard_enabled``
     - inference (GPT-OSS path enable)

A "switcheroo gotcha" comment at ``feature_service.py:56-60``
documents one rollout pitfall: when a per-tenant percentage rollout
is added, the Statsig rule's *EntityID / Hash by / Salting ID* must
be set to ``User ID`` rather than ``tenantId``. Hashing on
``tenantId`` makes the bucket constant per tenant — a 10% rollout
becomes 100% or 0% for any given tenant, never 10%. The codebase
does not enforce this; the comment is the only guardrail. Keep this
in mind when reading any rollout configuration in the Statsig
console.

Local overrides
---------------

``src/statsig_flags/local_overrides.py`` is a 24-line module. The
override file is a single JSON document with two top-level keys:

.. code-block:: json

   {
     "user": "test",
     "override": {
       "rai_api_prompt_moderation_v2": true
     }
   }

The example file at the repo root
(``feature_flag_overrides.example.json``) ships with exactly that
shape: a single user (``"test"``) and a single gate override
(``rai_api_prompt_moderation_v2: true``). The example gate name
(``rai_api_prompt_moderation_v2``) **does not appear in the
``Features`` enum** — it is a placeholder, not a current gate. Pick
a real gate name from the inventory above when copying the file.

Loading semantics:

* ``load_overrides_file`` (``local_overrides.py:15-23``) opens
  ``feature_flag_overrides.json`` (relative path; assumes the
  process's working directory is the repo root, which is how
  gunicorn is launched). On ``FileNotFoundError`` it logs a warning
  and returns an empty ``FlagOverridesFile``.
* The Pydantic model ``FlagOverridesFile`` has ``ConfigDict(extra="forbid",
  strict=True)`` (``local_overrides.py:9``) — extra keys cause a
  pydantic ``ValidationError`` on load. So a malformed overrides
  file is a startup failure, not a silent skip.
* In ``FeatureService.__init__`` the loaded overrides are applied
  via ``self.override_flag_for_user(overrides.user, key, value)`` —
  i.e. they are bound to a single ``atlassianAccountId``. Requests
  made on behalf of any other user **do not** see the override.
  This is intentional but easy to miss.

Mutator endpoints (admin blueprint)
-----------------------------------

Three routes mutate the Statsig override store at runtime, all
registered in ``src/api/v1/admin/admin_blueprint.py`` under
``/v1/admin/feature-flag/...``. They are **local-only** — every
handler is wrapped in ``@only_locally`` and returns
``("This endpoint is only available in local mode", 400)`` when
``config.is_local`` is false.

The full route list (with the underlying ``FeatureService`` call):

* ``POST /v1/admin/feature-flag/<user>/<flag_name>/enable`` →
  ``feature_service.override_flag_for_user(user, flag_name, True)``
  (``feature_service.py:94-103``).
* ``POST /v1/admin/feature-flag/<user>/<flag_name>/disable`` →
  ``feature_service.override_flag_for_user(user, flag_name, False)``.
* ``POST /v1/admin/feature-flag/<user>/<flag_name>/reset`` →
  ``feature_service.remove_override_for_user(user, flag_name)``
  (``feature_service.py:105-111``).

Both methods build a ``FeatureGateUser(FeatureGateUserAttributes(
atlassianAccountId=user))`` and call the SDK's
``override_gate`` / ``remove_gate_override`` directly. The override
state lives **in the SDK client's process memory** — a process
restart drops every runtime override, so the file-based mechanism
and the API-based mechanism solve different problems: the file is
how you persist a override across restarts; the API is how you
toggle one without restarting.

The full protocol shape (request/response bodies, status codes) is
documented in :ref:`api-reference` § *Admin*; the
:ref:`getting-started` page shows the exact ``curl`` invocations.

Per-request debug overrides
---------------------------

A third override mechanism exists, separate from the file and the
admin endpoints: ``FeatureService.set_request_overrides(overrides:
dict[str, bool])`` writes a dict onto Flask's ``g`` object
(``feature_service.py:113-121``). When ``_check_gate`` is called
later in the same request, it consults this dict *before* Statsig
(``feature_service.py:132-140``) and skips the SDK call entirely
if the gate is found.

This is the entry point that the moderation request schema's
``debug.featureGateOverrides`` field flows into (the read site is
discovered via ``get_request_overrides`` at
``feature_service.py:123-130``). Failures to access ``g`` (e.g.
during background tasks or test setup outside a Flask context) are
swallowed — ``get_request_overrides`` returns ``None`` rather than
raising — which keeps unit tests that exercise gates outside a
request context working.

Failure mode: Statsig unreachable
---------------------------------

The behaviour when Statsig is unreachable depends on *when* it is
unreachable:

* **At process boot.** ``FeatureService.__init__`` calls
  ``FeatureGateClient(...)`` synchronously. If the SDK's bootstrap
  raises, ``feature_service`` cannot be constructed and the import
  of ``src/feature_service.py`` fails. Since ``feature_service`` is
  a top-level singleton imported by ``app.py`` and many controllers,
  a hard SDK failure at boot is a hard service start-up failure.
  In production, the SDK has its own retry / cached-bootstrap
  policy; document the operational behaviour against the
  ``atlassian_feature_gate`` README rather than guessing here.
* **Per request.** ``_check_gate`` catches ``ValueError`` /
  ``TypeError`` / ``AttributeError`` / ``RuntimeError`` from the
  SDK and resolves to ``False``. **It does not catch
  ``Exception``** — so any exception type outside that list (e.g.
  a custom SDK exception, an unanticipated transport error) bubbles
  out and is caught by the ``@app.errorhandler(Exception)`` global
  handler, producing a 500. This is a real seam: the four caught
  classes are the historically-observed failure modes, not a
  guarantee. If a new SDK release surfaces a new exception class, a
  request-time outage can produce 500s instead of fail-closed
  ``False`` returns.
* **Tenant ID missing.** Independent of SDK reachability, a request
  whose ``X-Atlassian-CloudId`` is missing or blank flows
  ``cloud_id = ""`` through ``moderation_req_ctx_to_feature_attributes``;
  ``_check_gate`` short-circuits to ``False`` *before* calling
  Statsig. Combined with the controllers' ``required_headers`` 400
  guard, this is normally unreachable in production — but it is the
  reason in-process unit tests must construct a request context.

Dynamic config (per-tenant)
===========================

``src/dynamic_config/client.py`` is the project's wrapper around
the Atlassian dynamic-config SDK. The whole file is twenty lines
and doing exactly two things:

#. ``create_client()`` — a ``functools.cache``-wrapped factory that
   returns a singleton ``StatsigSidecarClient``. The cache decorator
   has no TTL and no maxsize argument, so the underlying client is
   built **once** per Python process. There is no health-check, no
   reconfigure path, no eviction.
#. ``get_all_service_configs(identifiers: Identifiers = Identifiers()) →
   ConfigCollection`` — calls
   ``config_client.get_configs(namespace="responsible-ai-api_server",
   identifiers=identifiers)``. The namespace string is the only
   coupling to the Atlassian dynamic-config registry; tenant-scoping
   is via the optional ``Identifiers(tenantId=...)`` argument.

This client is **not** wrapped by the project's ``time_cache`` —
the SDK itself does its own caching via the Statsig sidecar. The
60-second cache that the inference layer relies on is applied at the
*calling* site, not in this module:
``confidence/confidence_thresholds.py`` decorates its lookups with
``@time_cache(max_age=60)``.

Keys consumed today
-------------------

Two keys are referenced anywhere in the codebase, both from
``src/inference_models/confidence/confidence_thresholds.py``:

* ``responsible-ai-api-prompt-harm-thresholds`` — flat
  ``"slug:threshold"`` string list (legacy shape).
* ``responsible-ai-api-prompt-thresholds-by-version`` — JSON
  ``{ version_or_other: { slug: threshold } }``; lookup tries the
  exact ``model_evaluation_version`` first, then the literal
  ``"other"`` key, then raises.

Both keys are looked up per-tenant via
``Identifiers(tenantId=tenant_id)``. The schema, fallback semantics,
and the relationship to ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5`` are
documented in :ref:`inf-models` § *Confidence subpackage* — the
contract here is just "the dynamic-config client returns whatever
the sidecar holds for the given namespace and identifiers; the
caller owns parse and fallback policy."

Failure mode: dynamic config unreachable
----------------------------------------

The SDK propagates whatever the sidecar returns. The
``confidence/`` lookup wraps every call in a try/except that logs
and falls back to the empty default thresholds (i.e. every category
resolves to ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5``). So a sidecar
outage **degrades silently to a uniform threshold**, not to a 500.
This is the right shape — moderation degrades to a documented
behaviour rather than failing open or returning errors — but the
silence is worth knowing about: there is no metric for "dynamic
config fallback active." The 60-second cache also means a transient
outage can recover invisibly within one minute.

Auth context (slauth)
=====================

``src/slauth/user_context.py`` is **not** an authentication library
— it is a header parser. Inbound authentication (SLAUTH / ASAP) is
performed by the Atlassian edge proxy *before* the request reaches
this service. The proxy attaches a fixed set of ``X-Slauth-*``
headers; this module deserialises them.

That distinction matters: the service does **not** validate
JWTs in-process for inbound traffic. ASAP signing happens
*outbound* (via ``config.asap_signer``, used by the antiabuse
client and by Triton gRPC plugins) but never inbound.

Headers parsed
--------------

The header names come from the ``DownstreamHeaderNames`` enum
(``user_context.py:12-22``):

* ``X-Slauth-User-Context-Status`` — required; values ``"valid"``,
  ``"invalid"``, or ``"none"``. An unknown value is coerced to
  ``Invalid`` and logged (``user_context.py:29-32``).
* ``X-Slauth-User-Context`` — base64-encoded user context blob.
* ``X-Slauth-User-Context-Account-Id`` — Atlassian account ID.
* ``X-Slauth-User-Context-Request-Principal`` — user who made the
  request.
* ``X-Slauth-Issuer`` — system that authenticated the user.
* ``X-Slauth-Principal`` — the principal (user). The docstring at
  line 71 calls out that this is "often not set, so be careful using
  it." ``X-Slauth-Subject`` is also enumerated but not consumed
  anywhere today.

Parsing happens in ``get_user_context_from_incoming_headers()``
(``user_context.py:121-155``). If the status header is absent the
function short-circuits to ``SlauthUserContextHeaders(status=Missing)``
without reading the other headers — a clean signal that the
service-proxy ingress is misconfigured.

The two types
-------------

Two dataclass / class definitions cover the same fields with
different validity guarantees:

* ``SlauthUserContextHeaders`` (``user_context.py:56-118``) — the
  *parsed* form. All fields are ``Optional`` because a request might
  legitimately have ``status=Missing`` or ``status=Invalid`` with
  some fields blank. ``is_valid()`` returns
  ``status == SlauthUserContextStatus.Valid``.
* ``ValidSlauthUserContextHeaders`` (``user_context.py:35-53``) —
  the *narrowed* form, returned by
  ``valid_user_context()``. Its ``__post_init__`` raises
  ``ValueError`` if any of ``context``, ``account_id``,
  ``request_principal``, ``issuer``, *or* ``slauth_principal`` is
  empty. The ``slauth_principal`` requirement contradicts the
  docstring at line 71 ("often not set") — there is a real
  asymmetry: any caller that calls ``valid_user_context()`` on a
  request without ``X-Slauth-Principal`` will get a ``ValueError``.
  Callers must guard with ``is_valid()`` first **and** be prepared
  for the principal-missing case.

The ``__eq__`` on ``SlauthUserContextHeaders`` (``user_context.py:89-99``)
compares all six fields, but there is no ``__hash__`` — instances
are not safe to use as dict keys.

Tenant context (TCS)
====================

``src/tenant_context/tenant_context_client.py`` is the project's
client for the Tenant Context Service (TCS) sidecar. The
``__init__.py`` is empty; the only exported class is
``TenantContextClient``.

The client takes no constructor arguments — it reads
``config.tcs_url`` (composed from ``TCS_SIDECAR_HOST`` and
``TCS_SIDECAR_HTTP_PORT``, see `Static configuration`_). The default
URL is ``http://localhost:50050``, which assumes the TCS sidecar is
running in the same pod / process group as the service.

Three methods, all using ``requests.get`` with ``timeout=0.6`` (the
600 ms ``TIMEOUT`` constant at ``tenant_context_client.py:13``) and
``Accept: application/json``:

* ``get_organisation_id_from_cloud_id(cloud_id)`` — looks up the
  TCS *entity* under
  ``/entity/organization/ari:cloud:platform::site/{cloud_id}.ari.linked-org``
  and returns the ``orgId`` field. On non-200, on parse failure, or
  on any exception, returns ``None`` (logged).
* ``get_organisation_control_for_hosted_llms(org_id)`` — looks up
  the *settings* entity under
  ``/entity/settings_service/ari%3Acloud%3Aplatform%3A%3Aorg%2F{org_id}/atlassian-hosted-llms``
  and returns ``OrganisationSettings(org_id, enabled)``. The
  ``enabled`` field defaults to ``False`` if absent.
* ``get_hosted_llms_settings_for_cloud_id(cloud_id)`` — composes
  the previous two: cloud → org → settings. Returns ``None`` if
  either step fails or the org_id is empty.

The complete ARI-key vocabulary lives at the top of the file as
module-level constants (``TCS_ORG_ENTITY_TYPE``,
``TCS_KEY_LINKED_ORG_SUFFIX``, ``TCS_KEY_SITE_ARI_PREFIX``, etc.) —
notice the careful URL-encoding in
``TCS_KEY_ORG_ARI_ENCODED_PREFIX = "ari%3Acloud%3Aplatform%3A%3Aorg%2F"``;
the cloud-id key uses the *unencoded* form because Flask's
``requests`` library quotes path components, but the org-id key is
inserted into a path *segment* that already needs to look like an
encoded ARI to TCS, so the developer must pre-encode it.

There are **no retries**. There is **no circuit breaker**. The
client constructs a fresh ``requests`` connection per call (no
``Session`` reuse), so connection pooling is whatever
``requests.get`` defaults to.

Where is tenant context consumed?
---------------------------------

A grep across ``src/`` finds only one consumer today:
``src/service/moderation/agent/agent_moderation.py`` — the agent
moderation service calls
``tenant_context.get_hosted_llms_settings_for_cloud_id(cloud_id)``
when the ``rai_api_read_external_llm_calls_org_setting`` gate is on.
The result drives the agent service's external-LLM-blocking policy;
a missing setting (``None``) defers to the Statsig
``is_external_llm_calls_disabled`` gate. The full decision logic
lives in :ref:`svc-moderation`.

How auth + tenant context flow through a request
================================================

Five facts together describe how identity propagates:

#. **Tenant ID = ``X-Atlassian-CloudId``.** This is read by
   ``proxied_ai_gateway_headers()`` in the validate-header layer and
   becomes ``ModerationRequestContext.cloud_id``. Controllers call
   ``ModerationRequestContext.from_incoming_http_request()`` early
   (see :ref:`api-reference` § *Tenant context construction*); a
   missing cloud_id triggers an ``assert`` in
   ``moderation_request_context.py:75`` (in practice
   ``required_headers`` 400s the request first).
#. **Auth = ``X-Slauth-*`` headers.** Parsed by
   ``get_user_context_from_incoming_headers()`` (described above)
   and bundled into the same ``ModerationRequestContext`` as
   ``slauth_context_headers``. Both the cloud_id and the slauth
   headers are siblings in one dataclass.
#. **No Flask ``g``, no contextvars.** The
   ``ModerationRequestContext`` is held on the *call stack* — every
   service method that needs identity takes it as an explicit
   parameter (see ``agent_moderation.py:257``,
   ``image_moderation.py``, etc.). Two exceptions:

   * **Feature gates** read tenant + user from the request via
     ``ModerationRequestContext.from_incoming_http_request()``
     inside ``_check_gate`` (``feature_service.py:158-161``) — they
     re-derive the context rather than receive it. The implication
     is that ``feature_service`` cannot be used outside a Flask
     request context unless caller-provided overrides are set up
     first.
   * **Per-request debug overrides** sit on Flask ``g``
     (``feature_service.py:120, 127``).

#. **What's available where:**

   * **Controllers** (Layer 1): full ``ModerationRequestContext`` —
     constructed at the top of the route function. Controllers have
     access to ``request.headers`` directly as well, but the
     ``ModerationRequestContext`` is the canonical view.
   * **Services** (Layer 2): receive ``ModerationRequestContext``
     (or ``cloud_id`` + ``slauth_context_headers`` separately) as
     parameters. Services do **not** read Flask ``request`` directly.
   * **Inference layer** (Layer 3): receives only the data it needs.
     The AI Gateway path receives a ``HttpHeaders`` envelope built
     by ``ModerationRequestContext.to_ai_gateway_contract_http_headers()``
     (``moderation_request_context.py:38-52``); the Triton gRPC path
     does not propagate slauth at all (it injects its own ASAP JWT
     via ``TeamservePlugin``); SageMaker uses STS / boto3 default
     credentials. Identity is *not* threaded through the inference
     layer beyond the AI-Gateway header passthrough.

#. **Resolved user IDs.** ``ModerationRequestContext.resolve_user_ids()``
   returns a ``ResolvedUserIdentifiers(atlassian_account_id,
   anonymous_user_id)`` dataclass (``moderation_request_context.py:54-67``).
   It picks the slauth account ID if the slauth header set is valid;
   otherwise it falls back to the ``X-Atlassian-UserId`` header (the
   anonymous-user case). It raises ``ValueError`` if neither is
   available — analytics events have a strict invariant that
   exactly one of the two be set (see `Analytics: GASv3`_).

This propagation pattern is **clean and thread-safe** — there is no
shared mutable state — but it requires explicit parameter chaining.
Adding a new service method that needs identity means adding
``moderation_context: ModerationRequestContext`` to its signature
and threading it through.

Caching: ``time_cache``
=======================

``src/cache/time_cache.py`` is a 27-line decorator and the only
in-process caching utility the project owns. The implementation is
worth quoting in full because the trick is small:

.. code-block:: python

   def time_cache(max_age, maxsize=128, typed=False):
       def _decorator(fn):
           @functools.lru_cache(maxsize=maxsize, typed=typed)
           def _new(*args, __time_salt, **kwargs):
               return fn(*args, **kwargs)

           @functools.wraps(fn)
           def _wrapped(*args, **kwargs):
               return _new(*args, **kwargs, __time_salt=int(time.time() / max_age))

           _wrapped.cache_clear = _new.cache_clear
           return _wrapped
       return _decorator

The only ingredient is a *time salt* injected as a keyword argument
into a regular ``functools.lru_cache``. Once every ``max_age``
seconds, ``int(time.time() / max_age)`` increments by 1; the cache
key changes; the next call misses; the function recomputes. Old
entries linger in the ``lru_cache`` until LRU eviction kicks them
out, but they are unreachable because nobody asks for the previous
salt.

TTL semantics
-------------

* TTL boundaries are *aligned to wall-clock multiples of
  ``max_age``*, not relative to any specific call. With
  ``max_age=60``, every call between ``00:00:00`` and ``00:00:59``
  hits the same salt and shares cache; ``00:01:00`` rolls to a new
  salt regardless of the most recent miss. So a "60-second cache"
  is actually 1 to 60 seconds of effective TTL depending on when
  the first call lands within the bucket.
* There is no per-entry expiry. Eviction is **LRU on the underlying
  ``functools.lru_cache``** with ``maxsize=128`` (the default).
  Stale entries from previous salt buckets remain in memory until
  pushed out by new entries.
* Recompute on miss is **synchronous**. There is no background
  refresh, no stampede protection, no stale-while-revalidate.

What's cached today
-------------------

``time_cache`` has exactly two callers, both in
``src/inference_models/confidence/confidence_thresholds.py``:

* ``get_prompt_harm_confidence_thresholds(tenant_id)`` —
  ``@time_cache(max_age=60)`` over the flat string-list dynamic
  config ``responsible-ai-api-prompt-harm-thresholds``.
* ``get_prompt_harm_confidence_thresholds_by_model_version(tenant_id,
  model_evaluation_version, fallback_key="other")`` — same TTL,
  over the JSON dynamic config
  ``responsible-ai-api-prompt-thresholds-by-version``.

Nothing else uses ``time_cache``. The HTTP-side caching that
clients see is **not** backed by ``time_cache`` — it is the ETag
mechanism (see below). Connection-pool caching for HTTPX, AI
Gateway, gRPC, and SageMaker is handled by their respective SDK
clients, not by this module.

Thread / greenlet safety
------------------------

``functools.lru_cache`` is thread-safe at the CPython level (the GIL
covers the underlying dict mutations). The ``time_cache`` wrapper
adds nothing that would break that — the salt is a per-call
computation; both reads and writes go through ``_new``'s lru_cache.

Greenlet safety is the *same* as thread safety for in-CPython data
structures: the GIL is held across each individual ``__getitem__`` /
``__setitem__`` on the cache. There is no documented guarantee about
*compound* operations (e.g., "check then compute then insert") being
atomic with respect to gevent context switches at I/O boundaries —
but ``functools.lru_cache``'s critical section is short and contains
no I/O, so a stampede in practice means *N* greenlets recompute the
same value once and then *N - 1* of those computations are wasted
on insert (the cache stores whichever finishes first).

Cache stampede behaviour
------------------------

When the salt rolls over and concurrent requests miss simultaneously:

* All concurrent missers recompute the underlying function in
  parallel.
* There is **no thundering-herd suppression** — no semaphore, no
  "single-flight" pattern, no shared promise.
* For ``confidence/confidence_thresholds.py``, the underlying
  recomputation is a dynamic-config sidecar fetch. Concurrent
  recomputes fan out as concurrent ``get_configs`` calls. The
  sidecar is local (``localhost:50050`` by default) so the impact
  is bounded — but it is not zero.
* If a recompute *fails*, the exception propagates to the caller.
  ``confidence/`` itself wraps every call in a try/except that logs
  and falls back to defaults — so the stampede risk is "an extra
  fan-out of sidecar calls every minute," not "service crash."

Connection to the ETag mechanism
--------------------------------

``time_cache`` is **server-side** caching of *internal* lookups —
it makes the prompt-moderation hot path cheaper but is invisible to
clients. The ETag protocol is **client-side** caching of moderation
verdicts — the client caches the response body and the server
gates 304s on a hash of the request body and the model versions.

The two mechanisms are independent:

* ``time_cache`` reduces dynamic-config fetches; it does not affect
  the ETag computation.
* ETag computation does not consult any cached threshold; the hash
  ranges over the parsed request body and the *expected* model
  versions, not over thresholds.

The full ETag protocol — what is hashed, the weak-ETag form, the
``If-None-Match`` short-circuit, and the prompt-only scope —
lives in :ref:`api-etag`. The relevant fact for *this* page is just
that there is no shared cache between server-side
threshold caching and client-side response caching.

Exception model
===============

``src/exception.py`` is a small file (~106 lines) that defines one
typed exception (``APIException``) and one helper
(``make_api_error_response``). The *behavioural* contract — which
controllers catch what, how Flask routes errors to handlers — lives
in :ref:`architecture` § *Error and exception handling*. This page
documents the *types* and the *protocol*; the architecture page
documents the *handler chain*.

Class hierarchy
---------------

The hierarchy is intentionally flat. There is no project-wide base
``class ResponsibleAIError(Exception)`` and no rich subclass tree.
Three classes/families to track:

* ``APIException(HTTPException)`` (``exception.py:18-78``) — the
  one type that Flask's error pipeline routes specifically.
  Constructor takes ``message`` (becomes the ``description``),
  ``status_code`` (default 500, stored as ``self.code``), and
  optional ``headers`` (used for ``Retry-After`` on 429s).
* ``ImageModerationError(APIException)`` (defined in
  ``src/service/moderation/image/image_moderation.py``) — image
  service domain error; default 500. Subclass
  ``ImageProcessingError`` forces 400. **These are the only
  ``APIException`` subclasses in the project.** All other error
  types inherit from plain ``Exception``.
* ``PromptModerationError(Exception)`` (in
  ``src/inference_models/errors.py``) and its subclass
  ``MalformedModelOutput`` — see :ref:`inf-models`. These are
  inference-layer types that flow up through the
  ``inference_error_handler`` context manager and are translated to
  ``APIException`` (or to fail-open results) before reaching Flask.
* ``AgentModerationError(Exception)`` and its five subclasses
  (``AIGatewayCommsError``, ``MalformedModelOutputError``,
  ``NoCompletionsReturnedError``, ``NoMessageInCompletionError``,
  ``EmptyContentInMessageError``) defined in
  ``src/service/moderation/agent/agent_moderation.py``. These do
  **not** inherit from ``APIException`` — they fall through to the
  ``@app.errorhandler(Exception)`` global handler and become 500s.
  The ``exception_type`` field on these classes is consumed by the
  agent controller's metrics-tagging logic, not by the HTTP layer.

There are *two* unrelated classes named ``MalformedModelOutput`` /
``MalformedModelOutputError`` in the codebase
(``src/inference_models/errors.py`` and
``src/service/moderation/agent/agent_moderation.py`` respectively).
They share the name pattern but do not share a parent. This is a
known seam — the prompt and agent moderation paths grew their own
error vocabularies.

The ``proxied_statuses`` constant
---------------------------------

At ``exception.py:9-15`` a module-level list enumerates the HTTP
statuses that ``APIException.from_ai_gateway_error`` passes through
unchanged: 408, 429, 502, 503, 504. Anything else from the AI
Gateway collapses to a generic 500 with the message
``"Error from ai-gateway. Received status code: <n>"``. The 429 case
also propagates the upstream ``Retry-After`` header.

This is the whole AI Gateway → ``APIException`` translation
table. Other adapters (anti-abuse, TCS, SageMaker, Triton) do
**not** have a corresponding classmethod — their failures either
become ``APIException(503/504)`` via the
``inference_error_handler`` (Triton, SageMaker via the inference
layer) or are caught locally in their service-layer call sites
(antiabuse — see `Anti-abuse integration`_).

``to_metrics_outcome``
----------------------

``APIException.to_metrics_outcome()`` (``exception.py:45-50``) maps
the HTTP status to a metric tag value:

* 429 → ``"rate-limited"``
* 408 → ``"timeout"``
* anything else → ``"exception"``

Controllers call this when populating the ``outcome`` tag on the
moderation outcome and latency metrics. The mapping is the
*single* source of truth for "what does the dashboard see when this
exception escapes" — three buckets, no per-status fan-out.

The body shape
--------------

``make_api_error_response`` (``exception.py:81-105``) is the only
function that builds an error body, and the body is constant:

.. code-block:: json

   {
     "error": {
       "message": "...",
       "status_code": 500
     }
   }

When ``debug_trace`` is set on the exception (controllers attach it
when ``debug.verbose=true``), an additional top-level ``"trace"``
key is added with the ``DebugTrace`` model serialised via
``model_dump(exclude_none=True)``. This is the entire HTTP error
contract clients see — see :ref:`architecture` §
*Anatomy of APIException* for how the global handler chain gets
here, and :ref:`api-reference` for the response example.

How exceptions compose with the global handler
----------------------------------------------

``src/app.py`` registers five global handlers
(``@app.errorhandler(...)``) — the full registration list is in
:ref:`architecture` § *The five global handlers*. Summary:

* ``InternalServerError`` — werkzeug 500s with an underlying
  exception (e.g., a worker crash). Logs and renders the canonical
  error body. Picks up the ``debug_trace`` from
  ``original_exception``.
* ``APIException`` — delegates to ``error.get_response()`` which
  calls ``make_api_error_response`` with the exception's status,
  description, and ``debug_trace``.
* ``ValidationError`` (flask_pydantic) — 400 Bad Request with a
  shape that groups errors by parameter source.
* ``NotFound`` — 404 with the canonical "Endpoint not found." body.
* ``Exception`` — last-resort catch for anything else; logs with
  ``exc_info`` and returns 500.

The contract for raising code is therefore: raise ``APIException``
with the right status code if you want a typed-ish response; raise
anything else and accept a 500. The ``inference_error_handler``
context manager (see :ref:`inf-models`) is the bridge that
translates inference-layer transport errors into appropriate
``APIException`` codes before they escape the service boundary.

Analytics: GASv3
================

``src/gasv3_analytics/`` is the project's GASv3 (Atlassian's
operational analytics pipeline) emitter. The package has one client
and four event types:

.. code-block:: text

   src/gasv3_analytics/
   ├── rai_analytics_client.py        # RAIAnalyticsClient singleton
   └── events/
       ├── agent_moderation/agent_evaluated.py    # AgentEvaluatedEvent
       ├── image_moderation/image_evaluated.py    # ImageEvaluatedEvent
       ├── output_moderation/output_evaluated.py  # OutputEvaluatedEvent
       └── policy_filter/content_evaluated.py     # ContentEvaluatedEvent

The four directories under ``events/`` correspond to the four
moderation kinds documented in :ref:`api-reference` and
:ref:`svc-moderation`. Each directory holds a single ``*_evaluated``
module — the schema and the outcome enum for one moderation kind.
There are no other files in the package today.

The client
----------

``RAIAnalyticsClient`` (``rai_analytics_client.py:65-178``) wraps
the Atlassian ``analytics_client.client.Client`` SDK. Construction
takes one ``EnvType`` argument and configures the SDK with:

* ``env`` — mapped from ``EnvType`` to ``analytics_client.models.Env``
  (``rai_analytics_client.py:40-53``); ``LOCAL`` and ``UNKNOWN`` both
  map to ``Env.LOCAL``.
* ``product`` — the literal string ``"responsibleAI"``.
* ``subproduct`` — ``None`` (intentional).
* ``timeout`` — 2 seconds.
* ``max_retries`` — comes from ``RETRIES_BY_ENV_TYPE``
  (``rai_analytics_client.py:56-62``): ``UNKNOWN`` and ``LOCAL`` get
  0 retries; ``DEV`` and ``STAGING`` get 2; **``PROD`` gets 1**.
  Production has the lowest retry budget — a deliberate choice to
  cap analytics-side load when the upstream is degraded.

The client also constructs its own ``gevent.pool.Pool(10)``
(``DEFAULT_POOL_SIZE = 10``) for *outbound* dispatch. Each public
``send_*_event`` method builds an ``OperationalEvent``, then calls
``self._pool.spawn(self._send_event, event)`` — *the analytics
transmission is async / fire-and-forget on a per-process gevent
pool*. The HTTP path itself is whatever the SDK does (synchronous
within the spawned greenlet); from the controller's perspective the
call returns the moment the spawn enqueues.

``_send_event`` (``rai_analytics_client.py:80-88``) wraps the call
in try/except and **swallows every exception** as
``logger.error("Failed to send analytics event, event will not be
sent: %s", error)``. Combined with ``rai_api_disable_analytics``
(see `Statsig gate inventory`_), the analytics emission can never
escape and break a moderation request.

The four ``send_*_event`` public methods are also each wrapped in
their own outer try/except (``rai_analytics_client.py:96, 118, 140,
162``) to catch failures during ``OperationalEvent`` construction
itself — i.e. before the spawn — so e.g. a missing required
attribute on ``BaseEventAttributes`` becomes a logged error rather
than an HTTP 500. Each method is also instrumented with an
OpenTelemetry span via ``@tracer.start_as_current_span(...)``.

Event type table
----------------

Every event includes the ``BaseEventAttributes`` shared by all four
methods (``rai_analytics_client.py:26-37``):

* ``cloud_id: str`` — the tenant.
* ``user_id: Optional[str]`` — Atlassian account ID.
* ``anonymous_user_id: Optional[str]`` — fallback identifier.
* **Invariant:** exactly one of ``user_id`` / ``anonymous_user_id``
  must be set. The ``__post_init__`` raises ``ValueError`` if both
  are absent or both are present. Resolved via
  ``ModerationRequestContext.resolve_user_ids()``.

These three become the OperationalEvent's
``tenant_id`` / ``user_id`` / ``anonymous_id``. Per-kind attributes
are defined in the four event modules:

.. list-table:: GASv3 event types
   :header-rows: 1
   :widths: 22 18 25 35

   * - Method
     - Event class
     - Action / subject
     - Per-kind attributes
   * - ``send_content_evaluated_event``
     - ``ContentEvaluatedEvent``
     - ``contentEvaluated`` / ``policyFilter``
     - ``agentId`` (optional), ``detectedHarmCategory``,
       ``evaluationVersion``, ``outcome`` (Allowed/Disallowed),
       ``violationScore`` (optional), ``useCaseId`` (optional),
       ``slauthPrincipal`` (optional)
   * - ``send_image_evaluated_event``
     - ``ImageEvaluatedEvent``
     - ``imageEvaluated`` / ``imageModeration``
     - ``detectedHarmCategory``, ``outcome`` (Allowed/Disallowed),
       ``violationScore``, ``useCaseId``, ``slauthPrincipal``
   * - ``send_agent_evaluated_event``
     - ``AgentEvaluatedEvent``
     - ``agentEvaluated`` / ``agentModeration``
     - ``detectedHarmCategory``, ``evaluationVersion`` (composite
       ``"<model>:<prompt>"``), ``outcome``, ``useCaseId``,
       ``slauthPrincipal``
   * - ``send_output_evaluated_event``
     - ``OutputEvaluatedEvent``
     - ``outputEvaluated`` / ``outputModeration``
     - ``detectedHarmCategory``, ``evaluationVersion``, ``outcome``,
       ``streamId`` (required), ``chunkIndex`` (optional),
       ``violationScore``, ``useCaseId``, ``slauthPrincipal``

All event models use Pydantic ``ConfigDict(extra="forbid",
strict=True)`` and serialize with ``model_dump(by_alias=True)`` —
the JSON keys are the *aliased* camelCase names shown in the table,
not the Python snake_case attribute names.

The ``ContentEvaluatedEvent`` is what fires on the prompt-moderation
path — the historical action name is ``contentEvaluated`` /
``policyFilter`` to align with the older "policy filter" naming.
The newer event kinds (image / agent / output) get their own
``action_subject`` pairs.

Fire points
-----------

Each event fires from exactly one place:

* ``send_content_evaluated_event`` —
  ``src/api/v1/moderation/prompt_moderation_controller.py:136``
  (inside ``_process_prompt_moderation``, after a successful
  prediction).
* ``send_image_evaluated_event`` —
  ``src/api/v1/moderation/image_moderation_controller.py:130``
  (inside ``_process_image_moderation``, after the moderation
  response is built).
* ``send_agent_evaluated_event`` —
  ``src/api/v1/moderation/agent_moderation_controller.py:162``
  (inside ``_process_agent_moderation``, after a successful
  prediction).
* ``send_output_evaluated_event`` —
  ``src/service/moderation/output/stream_processor.py:84`` (per
  chunk inside the streaming output path — *one event per
  evaluated chunk*; ``streamId`` and ``chunkIndex`` make them
  correlatable).

The output path is the only one that fires *N* events per HTTP
request (one per chunk). The other three fire exactly one event per
successful request. None of the four fires on the failure path —
exceptions short-circuit before the analytics block. The single
shared kill-switch is ``feature_service.is_analytics_disabled()``
(gate ``rai_api_disable_analytics``); per the controllers
(:ref:`api-reference` § *Analytics emission*), failures inside the
analytics block are caught and logged but do not propagate.

PII and redaction
-----------------

The ``slauthPrincipal``, ``user_id``, ``anonymous_user_id``, and
``cloud_id`` fields are **PII-bearing**. They are sent as-is — no
hashing, no truncation, no in-process redaction. The user-input
text itself is **never** included in any event; only the verdict
(``detectedHarmCategory``, ``outcome``, ``violationScore``) and
identifiers travel.

Failure mode: analytics emit fails
----------------------------------

Three independent paths to "analytics did not emit":

#. **Gate disabled.** ``rai_api_disable_analytics`` (Statsig gate,
   default-off, on-flag → suppresses emission). The controllers
   wrap the analytics call in a check; when on, the spawn never
   happens.
#. **Construction failure.** ``BaseEventAttributes`` invariant
   violation (e.g., neither ``user_id`` nor ``anonymous_user_id``
   set) raises during the ``send_*_event`` outer try/except, is
   logged, and the request continues normally.
#. **Transport / SDK failure.** Anything raised from inside
   ``self._atl_analytics_client.operational(event)`` is caught in
   ``_send_event`` (``rai_analytics_client.py:80-88``) and logged.
   Crucially the *spawn itself* has already returned — the
   request is unblocked. There is no retry beyond the SDK's
   ``max_retries`` setting.

A consequence of the gevent pool being process-local: the pool size
is ``DEFAULT_POOL_SIZE = 10`` (``rai_analytics_client.py:23``). If
events arrive faster than the pool drains, ``Pool.spawn`` will
*block* the calling greenlet until a slot frees — i.e. the
controller's request greenlet stalls. There is no warn / drop
behaviour for pool saturation today; under sustained analytics-side
slowness, request latency is bounded by the analytics SDK. This is
worth knowing about during incident response.

Metrics: StatsD via FlaskMicros
===============================

``src/metrics/`` holds four files:

* ``metrics_handler.py`` — ``send_metric``, ``measure_latency``, the
  ``Metric`` registry, ``MetricTag`` enum, and the histogram-bucket
  constants.
* ``image_buckets.py`` — pixel-count → bucket-label mapping for
  image-moderation size metrics.
* ``prompt_moderation_metrics.py`` — outcome-metrics emitter +
  token-count / token-overflow bucket helpers + the
  ``derive_tags_from_result`` callback for prompt latency.
* ``output_moderation_metrics.py`` — outcome-metrics emitter for
  the streaming-output path.

The image and agent metrics emitters live in their respective
service / controller modules (image counters in
``src/service/moderation/image/image_moderation.py``; the agent
outcome counter in
``src/api/v1/moderation/agent_moderation_controller.py``), not under
``src/metrics/``. The metrics package is therefore a **toolkit**
plus *prompt-* and *output-* specific emitters; image and agent
emit by composing the toolkit themselves.

Wiring through ``FlaskMicros``
------------------------------

The architecture page documents the wiring for the broader
middleware stack (see :ref:`architecture` § *What FlaskMicros adds
at runtime* and § *Documented ambiguities*). The key fact for
metrics is:

* ``FlaskMicros(app)`` is invoked once at ``src/app.py:38``. That
  call installs the ``atlassian-flask-dogstatsd`` middleware.
* The middleware populates ``g.global_stat`` and ``g.host_stat`` on
  each request. ``g.global_stat`` is a duck-typed object exposing
  ``.timing(metric, value, tags)`` and ``.increment(metric, value,
  tags)`` methods.
* Project code reaches metrics via ``send_metric`` /
  ``measure_latency`` only. ``_send_metric``
  (``metrics_handler.py:198-209``) does
  ``getattr(g.global_stat, type.value)`` to pick between
  ``timing`` and ``increment``, then calls the resulting function
  with the metric name, value, and a list of stringified tags.

This means: **outside a Flask request context, ``send_metric`` will
fail on ``g.global_stat``** (Flask's ``g`` is empty / raises). In
production every emission site runs inside a request, so this is
mostly a test-discipline concern.

The default tag set
-------------------

``DEFAULT_TAGS = {MetricTag.REGION: config.micros_aws_region}``
(``metrics_handler.py:45``). Every metric sent through
``send_metric`` (the public wrapper) merges this into the per-call
tag dict before dispatch — so every metric carries a ``region:``
tag derived from ``MICROS_AWS_REGION``, defaulting to ``"unknown"``.
The Micros middleware adds further tags (host, version, service)
that this project does not duplicate.

Tag values flow through as ``f"{key.value}:{value}"`` strings.
``MetricTag`` (``metrics_handler.py:16-43``) enumerates 24 tag
keys. The ones used most are: ``outcome``, ``violation_score``,
``harm_category``, ``model_evaluation_version``,
``prompt_evaluation_version``, ``use_case_id``, ``slauth_issuer``,
``token_consumed_length``, ``token_overflow_ratio``,
``image_size_bucket``, ``image_type``, ``image_file_format``,
``circuit_breaker_state``, ``http_status_code``,
``retry_attempt_number``, ``retry_exception_type``, ``fail_open``,
``exception_raised``, ``httpx_pool_status``, ``region``.

The ``Metric`` registry
-----------------------

``Metric`` (``metrics_handler.py:144-184``) is a class whose class
attributes are the registered metric definitions. The full list,
grouped by domain:

.. list-table:: ``Metric`` registry
   :header-rows: 1
   :widths: 38 22 40

   * - Attribute
     - StatsD name
     - Notes
   * - ``AGENT_MODERATION_LATENCY``
     - ``agent_moderation.latency``
     - timing + histogram pair (100–2500 ms primary,
       3000–7500 ms high-range)
   * - ``AGENT_MODERATION_OUTCOME``
     - ``agent_moderation.outcome``
     - increment
   * - ``PROMPT_MODERATION_LATENCY``
     - ``prompt_moderation.latency``
     - same histogram-pair shape
   * - ``PROMPT_MODERATION_OUTCOME``
     - ``prompt_moderation.outcome``
     - increment
   * - ``PROMPT_NON_ALPHANUMERIC_RATIO``
     - ``prompt_moderation.non_alphanumeric_ratio``
     - increment, tagged with the
       ``non_alphanumeric_bucket``
   * - ``PROMPT_MODERATION_TOKEN_CONSUMED_LENGTH``
     - ``prompt_moderation.token_consumed_length``
     - increment
   * - ``PROMPT_MODERATION_TOKEN_OVERFLOW_RATIO``
     - ``prompt_moderation.token_overflow_ratio``
     - increment
   * - ``IMAGE_MODERATION_LATENCY``
     - ``image_moderation.latency``
     - timing + histogram pair
   * - ``IMAGE_MODERATION_OUTCOME``
     - ``image_moderation.outcome``
     - increment
   * - ``IMAGE_MODERATION_SIZE``
     - ``image_moderation.size``
     - increment, tagged with ``image_size_bucket``
   * - ``IMAGE_MODERATION_TYPE``
     - ``image_moderation.type``
     - increment
   * - ``IMAGE_MODERATION_FILE_FORMAT``
     - ``image_moderation.file_format``
     - increment
   * - ``OUTPUT_MODERATION_LATENCY``
     - ``output_moderation.latency``
     - timing + histogram pair
   * - ``OUTPUT_MODERATION_OUTCOME``
     - ``output_moderation.outcome``
     - increment
   * - ``ANTIABUSE_CIRCUIT_BREAKER_STATE``
     - ``image_moderation.antiabuse.circuit.breaker.state``
     - increment, tagged with the breaker state
   * - ``ANTIABUSE_REQUEST_SIZE``
     - ``image_moderation.antiabuse.request.size``
     - increment, tagged with ``request_size_bucket`` and
       ``antiabuse_operation``
   * - ``ANTIABUSE_RESPONSE_STATUS``
     - ``image_moderation.antiabuse.response.status``
     - increment, tagged with ``http_status_code``
   * - ``HTTPX_POOL_CONNECTIONS``
     - ``httpx.pool.connections``
     - emitted by the healthcheck — value is a count
   * - ``HTTPX_POOL_USAGE_RATIO``
     - ``httpx.pool.usage_ratio``
     - same — value is a percentage 0–100
   * - ``HTTP_CLIENT_RETRY``
     - ``http.client.retry``
     - increment, tagged with ``retry_attempt_number``,
       ``retry_exception_type``, ``use_case_id``
   * - ``GRPC_CIRCUIT_BREAKER_STATUS``
     - ``grpc.circuit_breaker.status``
     - increment with value 0/1; emitted by the healthcheck

The histogram-bucket strings (``MetricHistogramConstants``,
``metrics_handler.py:58-64``) are the static set passed as the
``gsd_histogram`` tag for SignalFx / Datadog histogram aggregation:
``100_250_500_750_1000_1250_1500_1750_2000_2500`` for the primary
range, ``3000_3500_4000_4500_5000_5500_6000_6500_7000_7500`` for
the high-range, and a default
``500_1000_..._40000`` bucket string for arbitrary timing metrics.
*Every* latency metric emits **three** statsd lines per call —
base ``timing``, plus the primary histogram, plus the high-range
histogram — see ``_send_duration_metrics``
(``metrics_handler.py:226-259``).

The image-size buckets
----------------------

``src/metrics/image_buckets.py`` defines a pixel-count threshold
table that drives the ``image_size_bucket`` tag. Boundaries are
powers of two: ``64×64`` (4K pixels) up through ``4096×4096`` (16M
pixels), with the labels ``"0-4K"``, ``"4K-16K"``, ``"16K-65K"``,
``"65K-262K"``, ``"262K-1M"``, ``"1M-4M"``, ``"4M-16M"``, and the
sentinel ``"16M+"`` for anything larger. The function
``get_image_size_bucket(width, height)`` walks the table in order
and returns the first label whose threshold the total pixel count
does not exceed.

This bucket lives on three image metrics
(``IMAGE_MODERATION_SIZE`` and the
``IMAGE_MODERATION_LATENCY`` ``derive_tags_from_result`` callback;
``IMAGE_MODERATION_OUTCOME`` is keyed on outcome / harm category,
not size). The intent is to attribute image-moderation latency to
a coarse size class without burning metric cardinality on
individual pixel counts.

Token buckets (prompt path)
---------------------------

``prompt_moderation_metrics.py`` (lines 83–159) defines two more
bucketing helpers used by ``derive_tags_from_result`` for the
prompt-moderation latency metric:

* ``get_token_consumed_bucket(token_count)`` — 30 buckets, fine-
  grained at low counts (``0-5``, ``6-10``, ..., ``901-1000``) and
  coarser as counts grow (``1001-2000``, ..., ``15001-16000``,
  ``16001+``). The fine resolution at low end matches typical
  prompt sizes and supports tracking growth in the long tail.
* ``get_token_overflow_ratio_bucket(ratio)`` — 11 buckets, ``0%``,
  ``1-10%``, ..., ``91-100%``, ``101-110%``, ..., ``191-200%``,
  ``200%+``. Since the ratio can exceed 100% (the prompt was longer
  than the model's context window even before truncation), buckets
  beyond 100% exist.

These tags appear on every successful prompt-moderation outcome
metric (they are derived from ``InferenceResult.consumed_tokens``
and ``InferenceResult.token_overflow_ratio`` returned from the
inference layer; see :ref:`inf-models` § *Model abstraction layer*).

``measure_latency``
-------------------

``measure_latency(definition, tags=..., derive_tags_from_result=...)``
(``metrics_handler.py:265-305``) is a decorator that wraps a
function with timing + histogram emission. The lifecycle:

#. ``time.perf_counter()`` snapshot at entry.
#. Run the function.
#. On exception: set ``exception_raised=True``, **re-raise**.
#. ``finally``: if ``derive_tags_from_result`` is supplied, call it
   with ``*args, result=result, **kwargs`` to extract tags from
   the (possibly ``None``) return value. Compute duration in ms.
   Send three metrics: timing, primary histogram, high-range
   histogram. Always merges in
   ``MetricTag.EXCEPTION_RAISED: str(exception_raised)`` plus
   ``DEFAULT_TAGS``.

The decorator is used by all four moderation controllers — see
:ref:`api-reference` § *Latency metric*. The
``derive_tags_from_result`` callback is what plugs in the per-kind
detail (harm category, model version, etc.) onto the latency
metric without coupling the decorator to any moderation kind.

Failure mode: metrics handler errors
------------------------------------

* ``send_metric`` outside a request context fails on
  ``g.global_stat`` (Flask's ``g`` is empty). Production code paths
  always run inside a request, so this is mostly a test-discipline
  concern.
* If the Datadog/SignalFx UDP packet drops, the call is silent —
  ``g.global_stat.timing`` / ``increment`` returns normally; the
  metric is simply lost. There is no per-call confirmation.
* If ``measure_latency`` is wrapped around a function that itself
  emits metrics in a ``finally`` block, the order of emission
  matters: the inner emission runs first (its own ``finally``),
  then the outer ``measure_latency`` ``finally`` emits the latency
  metrics. No deadlock risk; ordering is just informational.

ML platform: input moderation client
====================================

``src/ml_platform/`` is a small package — three files — that wraps
two pieces of integration with the Atlassian ML platform:

* ``input_moderation_client.py`` — the AI-Gateway-backed client for
  the legacy ``V2_3_3_prompt_v2`` Llama path (the AI-Gateway-based
  Pydantic shapes, plus the ``invoke_rai_ft_2_3_3`` SDK invocation
  shim).
* ``use_cases.py`` — a three-member enum
  (``AI_POLICY_FILTERING = "ai-policy-filtering"``,
  ``AGENT_MODERATION = "responsible-ai-agent-moderation"``,
  ``IMAGE_MODERATION = "responsible-ai-image-moderation"``).

The package is **only used by the inference layer** —
``src/inference_models/rai_llama.py`` constructs an
``RAIFTEndpointV2_3_3`` from the Pydantic shapes and the
SDK-invocation thunk; the AI Gateway HTTP transport itself is owned
by ``ai_gateway.client.sync.ClientWrapper``, configured one level up
in ``src/api/v1/moderation/app_context.py``.

What ``input_moderation_client.py`` actually exports
----------------------------------------------------

The module declares a small set of Pydantic models that describe
the AI-Gateway request / response shapes:

* ``ResponsibleAIFineTunedModelRequest(inputs: str, parameters:
  ResponsibleAIFineTunedModelParametersRequest)`` — the request
  body sent over HTTP. ``parameters`` carries
  ``do_sample``, ``return_full_text``, ``details`` (must be
  ``True`` to receive ``top_tokens``), and ``top_n_tokens=2``.
* ``ResponsibleAIFineTunedModelOutput`` — the response body, with
  ``generated_text`` (parsed as
  ``PromptModerationGeneratedText({category, toBeFiltered,
  violation_score?})``) and ``details`` (a
  ``PromptModerationDetails`` whose ``top_tokens`` list is what the
  Llama AI-Gateway path uses to compute the violation score; see
  :ref:`inf-models` § *AI Gateway invocation path*).
* ``ResponsibleAIFineTunedModelResponse`` — Pydantic ``RootModel``
  wrapping a ``List[ResponsibleAIFineTunedModelOutput]``.

The HTTP transport is **not** in this file. Hardcoded model IDs
(``"rai-ft-content-filter-v2-3-2"``,
``"rai-ft-content-filter-v2-3-3"``) appear at the top of the module
but the URL composition, auth, timeouts, retries, and circuit
breaker are owned by the AI Gateway SDK (instantiated in
``app_context.py``) — see :ref:`architecture` for the technology
choice and :ref:`inf-models` for how the call is dispatched.

The SDK retry config that this client opts into is
``app_context.custom_retry_config`` (tenacity, 2 attempts,
``wait_random_exponential(multiplier=1, min=0.5, max=1.5)``,
retrying only ``httpx.TimeoutException`` / ``httpx.NetworkError``;
HTTP 429s are *not* retried). The retry config is gated by
``feature_service.is_custom_retry_config_enabled()`` — see
`Statsig gate inventory`_.

When is this consumed?
----------------------

The client is consumed *only* on the prompt-moderation path, and
*only* when the Llama selector picks the AI-Gateway variant —
i.e. when both ``is_prompt_moderation_teamserve_v2_4_primary_enabled()``
and ``is_rai_ft_teamserve_primary_enabled()`` are off. The selector
logic lives in :ref:`inf-models` § *Selector and shadowing*.

``UseCases``
------------

``src/ml_platform/use_cases.py`` is six lines of enum:

.. code-block:: python

   class UseCases(Enum):
       AI_POLICY_FILTERING = "ai-policy-filtering"
       AGENT_MODERATION = "responsible-ai-agent-moderation"
       IMAGE_MODERATION = "responsible-ai-image-moderation"

The string values match the ``X-Atlassian-UseCaseId`` request
headers that the moderation endpoints accept (see
:ref:`api-reference` § *Required moderation headers*) — they are
the *call site* for picking which ML-platform use-case scope a
request belongs to. ``AIGatewayClient.sync()`` in
``app_context.py`` is configured with
``UseCases.AI_POLICY_FILTERING.value`` as the upstream
``USE_CASE_ID`` header for the prompt-moderation path.

A separate hard-coded list ``USE_CASE_IDS = ["ai-policy-filtering"]``
in ``feature_service.py:23`` is what
``feature_service.is_use_case_allowed()`` checks the inbound
``use_case_id`` against. The two sources are *not* unified — there
is one canonical list in ``feature_service.py`` and a separate
enum in ``ml_platform/use_cases.py``. Today they overlap on
``"ai-policy-filtering"`` only, but a new use-case allow-list entry
must be added in **both** places. Recorded in
`Documented ambiguities`_.

Anti-abuse integration
======================

``src/antiabuse/`` integrates the service with Atlassian's Abuse
Filescanner. Three files:

* ``antiabuse_client.py`` — the HTTPX client and circuit breaker.
* ``antiabuse_utils.py`` — request builders, classification
  mappers, validation helpers.
* ``models.py`` — Pydantic shapes for request / response.

The client is **only consulted from the image-moderation path**, in
parallel with the SageMaker-hosted V0/V1 image classifiers. The
service-layer orchestration lives in
``src/service/moderation/image/image_moderation.py`` (covered in
:ref:`svc-moderation`). What follows is the contract this layer
exposes.

The HTTP transport
------------------

``antiabuse_client.py`` is a thin HTTPX wrapper:

* Endpoint: ``POST {antiabuse_api_base_url}/api/moderation/scan``.
  The base URL is ``config.antiabuse_api_base_url`` (env var
  ``ANTIABUSE_API_BASE_URL`` with per-env defaults — see
  `Static configuration`_).
* Auth: ASAP JWT signed with audience ``"abuse-filescanner"`` via
  ``config.asap_signer.generate_jwt(...)``. If the signer fails or
  is unavailable, the client raises ``ValueError``.
* Timeouts: ``connect=read=write=pool=2.0s`` — all four phases the
  same. There is no per-phase tuning.
* Retries: **none built-in.** A bad call either succeeds, fails the
  HTTP status check, trips the breaker, or raises a transport
  error.
* Circuit breaker: ``pybreaker.CircuitBreaker`` with
  ``fail_max=5``, ``reset_timeout=60`` seconds, and an *exclusion
  rule* that prevents 4xx ``HTTPStatusError`` from counting as a
  failure. So upstream auth failures and bad-request 400s do not
  trip the breaker; only 5xxs and transport errors do. The breaker
  state is emitted as the
  ``image_moderation.antiabuse.circuit.breaker.state`` metric (see
  `Metrics: StatsD via FlaskMicros`_).

Errors in priority order:

* ``CircuitBreakerError`` from ``pybreaker`` (``HTTPClient`` calls
  inside the breaker context), logged + metric'd, re-raised.
* ``httpx.HTTPStatusError`` (4xx / 5xx with status check), logged
  + ``image_moderation.antiabuse.response.status`` metric'd by the
  status code, re-raised.
* ``httpx.RequestError`` (transport-level), logged, re-raised.
* ``ValueError`` from response validation, logged, re-raised.

The client does **not** swallow errors. The image-moderation
service does — its ``moderate_image`` call wraps the antiabuse call
in a try/except that returns ``None`` on failure. The split is
intentional: the client is a transport contract that surfaces
everything; the service decides whether to deflect or escalate.

Request and response shapes
---------------------------

``models.py`` declares:

* ``AntiAbuseClassification`` (StrEnum): ``MALICIOUS``,
  ``ILLICIT``, ``ABHORRENT``, ``PII``, ``COPYRIGHT``, ``NONE``.
* ``AntiAbuseConfidence`` (StrEnum): ``HIGH``, ``MEDIUM``, ``LOW``,
  ``SYNTHETIC``, ``NONE``.
* ``AntiAbuseOptionalFields`` — 14 optional fields (``text``,
  ``name``, ``size_in_bytes``, ``checksum``, ``mime_type``,
  ``upload_date``, ``org_id``, ``user_agent``, ``url``,
  ``cset_hash``, ``metadata``, etc.) with camelCase aliases for
  wire format (e.g. ``sizeInBytes`` → ``size_in_bytes``).
* ``AntiAbuseRequest`` — extends optional fields with six required
  ones: ``region``, ``platform``, ``file_id``, ``container_id``,
  ``user_id``, ``media`` (base64-encoded payload).
* ``AntiAbuseResponse`` — five identifier fields plus
  ``classification: AntiAbuseClassification`` and
  ``confidence: AntiAbuseConfidence``, plus an optional ``comment``.

``AntiAbuseOptionalFields`` is also referenced from the moderation
request schemas — see :ref:`api-reference` § *Image moderation*
where the ``image`` request body inherits these fields (they are
used by ``create_antiabuse_request`` to build the upstream call).

Helpers (``antiabuse_utils.py``)
--------------------------------

* ``validate_antiabuse_fields(...)`` — returns the list of missing
  required field names (``file_id``, ``container_id``, ``user_id``,
  ``region``, ``platform``); the controller calls this as a
  pre-flight check before any HTTP work.
* ``create_antiabuse_request(...)`` — builds the
  ``AntiAbuseRequest`` body. If the caller didn't supply
  ``size_in_bytes``, it decodes the base64 ``media`` to compute
  it; computes a SHA-256 ``checksum``; defaults ``upload_date`` to
  the current Unix timestamp.
* ``map_antiabuse_classification_to_image_harm(classification)`` —
  the static mapping used by the image moderation service to
  translate antiabuse verdicts into the ``ImageHarmCategory``
  vocabulary:

  * ``MALICIOUS → HATE_DISCRIMINATION``
  * ``ABHORRENT → VIOLENCE_HARASSMENT``
  * ``ILLICIT → ILLEGAL_ACTIVITY``
  * ``PII → PERSONALLY_IDENTIFIABLE_INFORMATION``
  * ``COPYRIGHT → INTELLECTUAL_PROPERTY``
  * ``NONE → NONE``

* ``map_antiabuse_confidence_to_score(confidence)`` — maps
  confidence to a numeric score: ``HIGH → 0.9``, ``MEDIUM → 0.7``,
  ``LOW → 0.5``, ``SYNTHETIC → 0.8``, ``NONE → 0.0``. This is a
  *fixed table*, not configurable. Image moderation's
  ``violation_score`` ends up as one of these five values when
  antiabuse takes the verdict.

Lifecycle and gating
--------------------

The antiabuse precheck is invoked from the image moderation
controller / service when **all three** of the following are true
(read site: ``app_context.py:50-54`` plus the image
controller / service):

* ``feature_service.is_use_case_allowed()`` — i.e. the request's
  ``use_case_id`` is one of the allow-listed values *or*
  ``is_enabled_for_developer()``;
* ``feature_service.is_image_moderation_v1_enabled()`` — V1
  classifier path is on;
* ``feature_service.is_image_moderation_antiabuse_enabled()`` —
  the antiabuse-specific gate.

When all three hold, antiabuse runs **in parallel with** image
classification (gevent greenlets, joined under
``config.greenlet_join_timeout``). When any of the three is off,
antiabuse is skipped entirely and the image path is V0/V1 only.

The verdict is consulted *request-side*, not analytics-side: when
antiabuse returns a non-``NONE`` classification, the image
moderation service **overrides the harm category and violation
score** that the SageMaker classifiers produced
(``ImageHarmCategory`` mapped from
``map_antiabuse_classification_to_image_harm``; violation score
from ``map_antiabuse_confidence_to_score``); when antiabuse
returns ``ABHORRENT``, the service additionally sets the
``deletion`` flag on the response. This means antiabuse can be the
*deciding* signal — image moderation's V0/V1 classifier output is
overruled. The full decision logic, including how failures of one
side affect the merged verdict, is in :ref:`svc-moderation` §
*Image moderation*.

Anti-abuse is **not** consulted on the prompt / output / agent
paths. Documented analytics-side hand-offs do not exist either —
the antiabuse output influences the synchronous moderation verdict
only.

Cross-cutting failure modes
===========================

The per-section "Failure mode" callouts above describe each
subsystem in isolation. The table below collects them in one place,
with the cross-system interactions that matter during incident
response.

.. list-table:: Cross-cutting failure modes
   :header-rows: 1
   :widths: 22 30 25 23

   * - Subsystem
     - What "down" looks like
     - Behaviour
     - Observable signal
   * - Statsig (boot)
     - SDK fails to bootstrap during ``FeatureService.__init__``
     - Hard import failure → ``feature_service`` cannot be
       constructed → ``app.py`` import fails → process does not
       start
     - Process not in service / container restart loop;
       ``GET /health-check`` never reachable
   * - Statsig (runtime)
     - Per-request gate check raises a caught exception type
     - ``_check_gate`` returns ``False`` (default-disabled
       behaviour); request continues, may take a different model
       path
     - "Error checking gate <name>: ..." log line; no metric
   * - Statsig (runtime, uncaught)
     - SDK raises an exception type *outside*
       ``(ValueError, TypeError, AttributeError, RuntimeError)``
     - Exception bubbles to ``@app.errorhandler(Exception)`` →
       HTTP 500
     - Generic 500s with the SDK exception in logs
   * - Tenant ID missing
     - Request lacks ``X-Atlassian-CloudId``
     - ``required_headers`` 400s the request before any gate is
       checked; in test contexts where the guard is bypassed,
       every gate defaults to ``False``
     - 400 response; gate-check log lines saying "tenantId is
       None"
   * - Dynamic config sidecar
     - TCS sidecar / Statsig dynamic-config sidecar unreachable
     - ``confidence/`` lookups log + fall back to
       ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5`` for every category;
       moderation continues at uniform threshold
     - Logged warnings; **no metric** for fallback active
   * - Dynamic config (cache stampede)
     - Salt rolls; many concurrent missers
     - All fan out to the sidecar in parallel; eventual
       convergence; ~1× per minute per process
     - Spike in sidecar QPS at minute boundaries
   * - Analytics (transport)
     - GASv3 SDK transport fails
     - Caught + logged in ``_send_event``; spawned greenlet drops
       the event silently
     - "Failed to send analytics event" log lines
   * - Analytics (pool full)
     - ``DEFAULT_POOL_SIZE = 10`` saturated; events arriving
       faster than they drain
     - **``Pool.spawn`` blocks** the calling request greenlet until
       a slot frees → request latency tied to analytics latency
     - Latency metrics climb on the four moderation endpoints with
       no upstream model latency change
   * - Metrics handler
     - StatsD UDP packet drop / aggregator down
     - ``send_metric`` call returns normally; metric is silently
       lost
     - Drop in observed metric volume on dashboards (no in-process
       signal)
   * - Metrics handler (no Flask context)
     - Background task / test calls ``send_metric`` outside a
       request context
     - ``getattr(g.global_stat, ...)`` fails because ``g`` is
       empty; raises
     - Test failure or exception in any background-task code; not a
       production concern
   * - Anti-abuse (circuit open)
     - Five consecutive 5xx / transport errors in 60 s
     - Breaker opens; subsequent calls raise
       ``CircuitBreakerError`` immediately; ``image_moderation``
       service catches and decides whether to proceed (image V0/V1
       result) or fail
     - ``image_moderation.antiabuse.circuit.breaker.state = "open"``
       metric; Splunk-side logged exceptions
   * - Anti-abuse (auth fail / 4xx)
     - ASAP signer broken or upstream rejects with 4xx
     - Breaker does **not** count the failure (4xx exclusion); the
       call fails per-request with no breaker action
     - ``image_moderation.antiabuse.response.status`` metric tagged
       with the 4xx code; per-request log lines
   * - ML-platform / AI-Gateway (timeout)
     - Llama AI-Gateway path timing out
     - ``inference_error_handler`` may fail-open at 0.5 if
       ``should_fail_open_on_model_timeout`` is on; otherwise 504
     - ``http.client.retry`` metric increments; ``fail_open`` tag
       on outcome metric
   * - Triton circuit breaker
     - 30 consecutive failures on a Triton client instance
     - Per-instance breaker opens; calls raise
       ``CircuitBreakerError``; ``inference_error_handler`` may
       fail-open at 0.0 if ``should_fail_open_if_circuit_breaker_open``
       is on; otherwise 503
     - ``GRPC_CIRCUIT_BREAKER_STATUS = 0`` from healthcheck;
       ``grpc.circuit_breaker.status`` time series
   * - TCS sidecar
     - Sidecar request returns non-200 or transport error
     - ``TenantContextClient`` returns ``None`` (logged); the agent
       service's external-LLM logic falls back to the Statsig
       gate
     - "TCS returned status code N..." warning logs

Two interactions deserve their own bullets because they are easy to
miss when reading a single section:

* **Statsig + dynamic config can fail independently.** Statsig
  (gates) and the dynamic-config sidecar (per-tenant numerics) are
  *different* sidecars / SDKs. A Statsig outage and a dynamic-config
  outage produce different symptoms (gates default to false vs
  thresholds default to 0.5). The two are not co-failing in
  general.
* **Analytics pool saturation looks like upstream slowness.** A
  full ``Pool(10)`` blocks ``send_*_event`` until a slot frees —
  the moderation request greenlet stalls until the spawn enqueues.
  In an incident this presents as "moderation latency climbed but
  the upstream model is fine"; the actionable mitigation is to
  flip ``rai_api_disable_analytics`` on, which shorts the spawn
  entirely.

Cross-references
================

Backward (foundation pages this page resolves)
-----------------------------------------------

* :ref:`introduction` — service purpose / scope. Sets the
  expectations this page operationalises.
* :ref:`getting-started` — local toolchain, run modes, and the
  ``feature_flag_overrides.json`` workflow. The :ref:`gs-feature-flags`
  section in particular is the developer-laptop counterpart of
  `Local overrides`_ and the admin endpoints.
* :ref:`architecture` — full request lifecycle, blueprint tree,
  the FlaskMicros wiring, and the global error-handler chain. This
  page assumes the architecture document for layer ordering, the
  blueprint URL prefixes, and the error-handler contract.
* :ref:`api-reference` — the public HTTP contract. Specifically:

  * § *Admin* enumerates the three feature-flag override endpoints
    that this page documents the *backend* of.
  * § *ETag handling* (anchor :ref:`api-etag`) is the client-side
    cache mechanism that pairs with `Caching: time_cache`_.
  * § *Required moderation headers* and § *Tenant context
    construction* describe the headers this page parses in
    `Auth context (slauth)`_ and `Tenant context (TCS)`_.
  * § *Latency metric* and § *Analytics emission* describe how
    controllers consume the helpers in `Metrics: StatsD via
    FlaskMicros`_ and `Analytics: GASv3`_.

Forward (consumers of these modules)
------------------------------------

* :ref:`svc-moderation` — the four moderation services. Consumers
  of every gate, every metric, every analytics event, and the
  ``ModerationRequestContext`` propagation pattern. The
  external-LLM-blocking decision in agent moderation specifically
  consumes ``TenantContextClient``.
* :ref:`inf-models` — the inference layer. Consumes the
  model-version flags
  (``is_prompt_moderation_teamserve_v2_4_primary_enabled``,
  ``is_rai_ft_teamserve_primary_enabled``,
  ``is_gpt_oss_safeguard_enabled``,
  ``is_image_moderation_v1_enabled``,
  ``is_use_case_allowed``,
  ``is_shadow_with_teamserve_v2_4_enabled``,
  ``is_rai_ft_teamserve_shadowing_enabled``,
  ``is_shadow_with_ai_gateway_2_3_3_enabled``,
  ``should_fail_open_on_model_timeout``,
  ``should_fail_open_if_circuit_breaker_open``,
  ``is_strict_tokenization_failure_enabled``,
  ``is_increased_input_clipping_buffer_enabled``,
  ``is_standardized_image_moderation_response_enabled``,
  ``is_custom_retry_config_enabled``); the dynamic-config keys
  ``responsible-ai-api-prompt-harm-thresholds`` and
  ``responsible-ai-api-prompt-thresholds-by-version``; the static
  config knobs ``image_moderation_v0_threshold``,
  ``image_moderation_v1_threshold``, ``inference_pool_size``,
  ``greenlet_join_timeout``, ``sm_endpoint_image_moderation``,
  ``sm_endpoint_image_moderation_v1``, ``teamserve_endpoint``,
  ``teamserve_gptoss_endpoint``; and ``config.asap_signer`` for
  outbound JWT signing.

Documented ambiguities
======================

Items surfaced while authoring this page. They mirror the
``Documented ambiguities`` blocks in :ref:`introduction`,
:ref:`getting-started`, and :ref:`architecture` so each page
stands on its own.

#. **``ENABLE_RESPONSE_HANDLING`` is unused.** The
   ``Features`` enum at ``feature_service.py:38`` declares the
   gate string ``"rai_api_enable_response_handling"`` but no
   ``FeatureService`` method references it and no caller anywhere
   in ``src/`` reads it. The gate cannot affect runtime today.
   Either delete the enum member or wire a method around it; do
   not add gate-evaluation code anywhere else under the assumption
   it is connected.

#. **``Config._required_vars`` is empty.** The constructor at
   ``config.py:91`` initialises the list to ``[]`` and
   ``check_required_vars_are_set`` is a no-op until something
   populates it. The ``NO_CHECK_REQUIRED_VARS`` env-var skip is
   therefore vestigial. If the project intends a "fail fast on
   missing critical env" guard, the list needs to be filled in
   (e.g., ``["MICROS_ENVTYPE", "ASAP_ISSUER", ...]``).

#. **Two ``Use case`` / ``UseCases`` allow-lists.**
   ``feature_service.USE_CASE_IDS = ["ai-policy-filtering"]`` is
   the inbound allow-list checked by ``is_use_case_allowed()``,
   while ``ml_platform.use_cases.UseCases`` is a separate
   enumeration with three values. The two overlap on
   ``"ai-policy-filtering"`` only. A new accepted use case must be
   added in **both** places. Ideally ``feature_service`` would
   import and iterate ``UseCases`` rather than duplicating the
   string literal.

#. **``ValidSlauthUserContextHeaders`` requires
   ``slauth_principal``.** The class docstring at
   ``user_context.py:71`` says "often not set, so be careful using
   it" — but ``ValidSlauthUserContextHeaders.__post_init__`` at
   ``user_context.py:52-53`` raises ``ValueError`` if the field is
   empty. Calling ``valid_user_context()`` on a request that
   lacks ``X-Slauth-Principal`` therefore raises. Callers must
   either guard with both ``is_valid()`` *and* a presence check on
   ``slauth_principal``, or the validity contract should be
   relaxed.

#. **``rai_api_prompt_moderation_v2`` in the example overrides
   file does not match a current gate.** The example file at
   ``feature_flag_overrides.example.json`` overrides a gate named
   ``rai_api_prompt_moderation_v2`` which does not appear in the
   ``Features`` enum. It is a placeholder; copying the file
   verbatim into ``feature_flag_overrides.json`` and starting the
   service produces a "gate not in the rule list" no-op rather
   than a useful local override. Pick a real gate name from
   `Statsig gate inventory`_ when adapting the example.

#. **No metric for "dynamic-config fallback active."** The
   confidence-threshold lookup degrades silently to
   ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5`` if the dynamic-config
   sidecar fails. There is no counter, no gauge, no log-derived
   metric for "served the default thresholds because the sidecar
   was unreachable." If this is a meaningful operational signal,
   it would have to be added to ``confidence/confidence_thresholds.py``.

#. **Connection-pool semantics for ``TenantContextClient``.** The
   client constructs a fresh ``requests.get`` per call without a
   persistent ``Session``. Connection re-use is whatever the
   ``requests`` defaults provide. If high-volume agent-moderation
   traffic emerges, this is a candidate for a session-backed
   refactor.

#. **Antiabuse 4xx exclusion in the breaker.** The breaker in
   ``antiabuse_client.py`` excludes 4xx status from failure
   counting. This protects against breaker tripping on persistent
   400/401 (e.g., ASAP signer outage), but it also means a stuck
   401 will neither trip the breaker nor self-heal — every
   subsequent request retries the same failing call. If a 4xx
   regression should escalate, an explicit alert on
   ``image_moderation.antiabuse.response.status:4xx`` is the only
   guardrail today.

Verification anchors
====================

The following claims were verified directly against source. Each
entry points to the file and a representative location so a reader
can re-check by hand.

* ``config.py`` — singleton constructed at module import
  (``config.py:182``); env-var inventory matches the
  ``Config.__init__`` body (``config.py:43-148``); ASAP validation
  at ``config.py:107-123`` raises ``ValueError`` on missing
  issuer / private key when not in local mode with
  ``NO_ASAP_SIGNER=true``; ``_required_vars = []`` at
  ``config.py:91``; ``parse_version_json`` reads
  ``build-output/git-version.json`` and
  ``build-output/release-version.json`` (``config.py:170-179``).

* ``feature_service.py`` — 26 gate strings in the ``Features``
  enum (``feature_service.py:26-61``); 25 backing methods on
  ``FeatureService`` (one orphan: ``ENABLE_RESPONSE_HANDLING``);
  ``_check_gate`` short-circuits on per-request overrides
  (``feature_service.py:132-140``) and on missing tenant ID
  (``feature_service.py:145-150``); the four caught SDK exception
  types are ``(ValueError, TypeError, AttributeError, RuntimeError)``
  (``feature_service.py:154-156``); ``USE_CASE_IDS = ["ai-policy-filtering"]``
  at ``feature_service.py:23``; ``override_flag_for_user`` at
  ``feature_service.py:94-103`` calls ``self._client.override_gate``
  with a ``FeatureGateUser(atlassianAccountId=...)``.

* ``statsig_flags/local_overrides.py`` — 24-line file;
  ``FlagOverridesFile`` has ``ConfigDict(extra="forbid",
  strict=True)``; ``load_overrides_file`` returns an empty
  ``FlagOverridesFile`` on ``FileNotFoundError`` (logged warning).

* ``feature_flag_overrides.example.json`` — single user
  ``"test"``, single override
  ``{"rai_api_prompt_moderation_v2": true}``; gate name does not
  appear in the ``Features`` enum (placeholder).

* ``dynamic_config/client.py`` — twenty lines; ``create_client``
  is ``functools.cache``-wrapped (singleton, no TTL);
  ``get_all_service_configs`` calls
  ``get_configs(namespace="responsible-ai-api_server", ...)``.

* ``slauth/user_context.py`` — six headers in
  ``DownstreamHeaderNames`` (plus ``SlauthSubject`` enumerated
  but not consumed); ``SlauthUserContextStatus`` has three values
  (``Missing``, ``Invalid``, ``Valid``);
  ``ValidSlauthUserContextHeaders.__post_init__`` raises if any of
  five fields including ``slauth_principal`` is empty
  (``user_context.py:43-53``).

* ``tenant_context/tenant_context_client.py`` — ``TIMEOUT = 0.6``
  (600 ms); three methods, no retries, no breaker; ARI key
  constants at ``tenant_context_client.py:7-12``.

* ``cache/time_cache.py`` — 27 lines; ``__time_salt`` keyword
  injected via ``int(time.time() / max_age)``; underlying
  ``functools.lru_cache(maxsize=128, typed=False)``; only callers
  are in ``inference_models/confidence/confidence_thresholds.py``.

* ``exception.py`` — 106 lines; one ``APIException`` class;
  ``proxied_statuses`` at ``exception.py:9-15`` is exactly
  ``[429, 502, 503, 504, 408]``; ``to_metrics_outcome`` returns one
  of ``{"rate-limited", "timeout", "exception"}``;
  ``make_api_error_response`` body shape matches the JSON in `The
  body shape`_.

* ``gasv3_analytics/rai_analytics_client.py`` — four
  ``send_*_event`` methods at lines 93/115/137/159; each
  ``self._pool.spawn(self._send_event, event)`` then catches outer
  exceptions; ``DEFAULT_POOL_SIZE = 10``;
  ``RETRIES_BY_ENV_TYPE = {UNKNOWN:0, LOCAL:0, DEV:2, STAGING:2,
  PROD:1}``.

* ``gasv3_analytics/events/policy_filter/content_evaluated.py`` —
  ``ContentEvaluatedEvent`` carries ``agentId``,
  ``detectedHarmCategory``, ``evaluationVersion``, ``outcome``,
  ``violationScore``, ``useCaseId``, ``slauthPrincipal``; outcome
  enum has two values; ``ConfigDict(extra="forbid", strict=True)``.
  The other three event modules follow the same pattern.

* ``metrics/metrics_handler.py`` — ``Metric`` registry has 21
  named entries (``metrics_handler.py:144-184``); 24
  ``MetricTag`` enum members (``metrics_handler.py:16-43``);
  ``DEFAULT_TAGS = {REGION: config.micros_aws_region}`` at
  ``metrics_handler.py:45``; ``measure_latency`` emits three
  metrics per call (timing + primary histogram + high-range
  histogram).

* ``metrics/image_buckets.py`` — eight buckets
  ``[64×64, 128×128, 256×256, 512×512, 1024×1024, 2048×2048,
  4096×4096]`` plus ``"16M+"`` sentinel; labels match the table in
  `The image-size buckets`_.

* Fire-points for analytics events: ``send_content_evaluated_event``
  at ``prompt_moderation_controller.py:136``;
  ``send_image_evaluated_event`` at
  ``image_moderation_controller.py:130``;
  ``send_agent_evaluated_event`` at
  ``agent_moderation_controller.py:162``;
  ``send_output_evaluated_event`` at
  ``stream_processor.py:84`` — all confirmed by grep across
  ``src/``.

* Admin feature-flag endpoints — three routes at
  ``src/api/v1/admin/admin_blueprint.py:22, 29, 36``, each wrapped
  in ``@only_locally`` and bound to
  ``feature_service.override_flag_for_user`` /
  ``feature_service.remove_override_for_user``.

* ``ml_platform/use_cases.py`` — three enum values:
  ``"ai-policy-filtering"``,
  ``"responsible-ai-agent-moderation"``,
  ``"responsible-ai-image-moderation"``.

* ``antiabuse/antiabuse_client.py`` — ``CircuitBreaker(fail_max=5,
  reset_timeout=60, exclude=...)`` with 4xx exclusion; HTTPX
  timeouts ``connect=read=write=pool=2.0``; ASAP audience
  ``"abuse-filescanner"``.

* ``antiabuse/antiabuse_utils.py`` — six classification mappings
  (table in `Helpers (antiabuse_utils.py)`_); five confidence-to-
  score mappings (``HIGH:0.9, MEDIUM:0.7, LOW:0.5, SYNTHETIC:0.8,
  NONE:0.0``).

* ``antiabuse/models.py`` — ``AntiAbuseClassification`` has six
  values; ``AntiAbuseConfidence`` has five values;
  ``AntiAbuseRequest`` has six required fields (``region``,
  ``platform``, ``file_id``, ``container_id``, ``user_id``,
  ``media``).
