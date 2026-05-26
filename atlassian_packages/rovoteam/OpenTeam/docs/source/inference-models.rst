.. _inf-models:

================
Inference Models
================

.. note::

   This page documents the ``src/inference_models/`` package — the layer
   that owns *how* the moderation service talks to text and image
   classifier models. For where this layer sits in the overall request
   path, see :ref:`architecture`. For the orchestrating service that
   decides *when* to call which model and turns a model response into a
   moderation verdict, see :ref:`svc-moderation`. For the runtime
   feature flags that select model versions and toggle shadowing, see
   :ref:`config-overview`.

.. contents::
   :local:
   :depth: 2

Purpose & scope
===============

The ``inference_models`` package is the *only* place in the codebase
that owns wire-level concerns for ML model invocation. Everything
above it (controllers, the moderation services, business rules) talks
to models through transport-agnostic Python types in
``model.py``; everything below it (Triton gRPC, Triton's OpenAI-
compatible HTTP path, SageMaker, HuggingFace tokenizers) is hidden
behind that boundary.

In concrete terms, the package answers four questions:

#. **Which model do we call?** — selected per-request by feature flags
   evaluated in ``RAILlamaModels.get_model()`` /
   ``RAIGPTOSSModels.get_model()`` (text path) and in
   ``ImageModerationSageMaker.run_inference`` (image path).
#. **How do we serialize the call?** — Triton gRPC for the in-Teamserve
   Llama models, Triton's OpenAI-compatible HTTP path for GPT-OSS
   Safeguard, the AI Gateway for the legacy ``V2_3_3_prompt_v2`` Llama
   path, and the SageMaker runtime API for image moderation.
#. **Is the score actionable?** — answered by the
   ``confidence/`` subpackage, which loads per-tenant per-category
   thresholds from Atlassian dynamic config.
#. **Should we evaluate a candidate in parallel?** — answered by the
   ``model_shadowing/`` subpackage, which runs a second model in a
   gevent greenlet alongside the primary and *logs* the comparison
   without affecting the response.

The layer does **not** own retry policy: HTTP retries on the AI
Gateway path live in ``api/v1/moderation/app_context.py`` (tenacity,
2 attempts, ``wait_random_exponential(0.5–1.5s)``). The package
*does* own circuit breaking — both Triton clients use a
``pybreaker.CircuitBreaker(name="triton_circuit_breaker", fail_max=30)``.

Module layout
=============

.. code-block:: text

   src/inference_models/
   ├── model.py                      # base abstractions: InferenceModel, ModelEndpoint, tokenizer, prompt template
   ├── errors.py                     # exception taxonomy (just two classes)
   ├── error_handling.py             # fail-open context manager (NOT a retry decorator)
   ├── image_moderation_types.py     # pydantic shapes + image constants
   ├── rai_llama.py                  # three Llama variants (gRPC + AI-Gateway) + shadow plumbing
   ├── rai_gpt_oss.py                # GPT-OSS Safeguard 20b via Triton OpenAI HTTP
   ├── image_moderation_sagemaker.py # V0 (legacy detector) + V1 (ShieldGemma) on SageMaker
   ├── sagemaker_base.py             # boto3 sagemaker-runtime wrapper, assume-role fallback
   ├── triton_grpc_client.py         # GrpcEndpoint + TeamservePlugin (ASAP JWT)
   ├── triton_openai_api_client.py   # TritonOpenAIClient (requests + JWTAuth)
   ├── confidence/
   │   ├── __init__.py
   │   └── confidence_thresholds.py  # tenant-specific, dynamic-config-driven
   └── model_shadowing/
       ├── __init__.py               # empty
       └── shadower.py               # ModelShadower, ShadowEvaluator, ShadowShim

Tokenizer assets do **not** live under ``src/inference_models/``. They
sit at the project root in ``tokenizers/`` and are loaded by the
factories in ``rai_llama.py`` / ``rai_gpt_oss.py`` via relative paths
like ``"tokenizers/rai_ft_v2_2"`` (so the working directory must be
the project root at startup — which is how the gunicorn/Flask process
is launched, see :ref:`architecture`).

There is no top-level ``__init__.py`` for the package today;
consumers reach into the modules directly (e.g.
``from src.inference_models.rai_llama import create_rai_llama_models``).

.. list-table:: File-to-role map
   :header-rows: 1
   :widths: 30 18 52

   * - File
     - Role
     - Notes
   * - ``model.py``
     - Abstraction
     - Generic base classes ``InferenceModel[U,P]`` (top-level entrypoint
       returning ``InferenceResult[U]``) and ``ModelEndpoint[T,U,P]``
       (the wire send). Also owns ``ModelTokenizer`` / ``HFPretrainedModelTokenizer``
       and ``ModelPromptTemplate``.
   * - ``errors.py``
     - Abstraction
     - Two classes: ``PromptModerationError`` (base) and ``MalformedModelOutput``.
   * - ``error_handling.py``
     - Abstraction
     - ``inference_error_handler`` context manager. Fail-open on timeouts
       / circuit-breaker open / malformed output (gated by feature flags);
       otherwise re-raises as ``APIException`` with an HTTP status code.
   * - ``image_moderation_types.py``
     - Abstraction
     - Constants (``HUMAN_CLASS_ID = 0``, ``MODERATION_THRESHOLD = 0.4``)
       plus three pydantic models (``ImageModerationOutputV0``,
       ``ImageModerationOutputV1``, ``ResponseAIImageResponse``).
   * - ``rai_llama.py``
     - Concrete clients
     - ``LlamaModel`` (AI-Gateway transport) + ``LlamaModelInTeamserve``
       (Triton gRPC) + factory ``create_rai_llama_models`` returning
       three variants and a feature-flag-driven selector.
   * - ``rai_gpt_oss.py``
     - Concrete client
     - ``GPTOSSModelInTeamserve`` over Triton's OpenAI-compatible HTTP path.
   * - ``image_moderation_sagemaker.py``
     - Concrete clients
     - V0 (boxes/scores detector) + V1 (ShieldGemma); runs them in
       parallel via gevent when V1 is enabled.
   * - ``sagemaker_base.py``
     - Transport (shared)
     - ``SageMakerInferenceBase``: lazy boto3 ``sagemaker-runtime`` client
       with an assume-role fallback to ``arn:aws:iam::540824312222:role/SageMakerExecutionRole``.
   * - ``triton_grpc_client.py``
     - Transport
     - ``TeamservePlugin`` (auth + Teamserve headers) + ``GrpcEndpoint``
       with circuit breaker, used only by Llama Teamserve variants.
   * - ``triton_openai_api_client.py``
     - Transport
     - ``TritonOpenAIClient``: ``requests.post`` to ``/v1/chat/completions``
       with JWTAuth and the same circuit-breaker name.
   * - ``confidence/confidence_thresholds.py``
     - Decision logic
     - ``PromptHarmConfidenceThreshold`` / ``PromptHarmConfidenceThresholds``
       loaded from Atlassian dynamic config, cached for 60s. **No
       calibration module exists.**
   * - ``model_shadowing/shadower.py``
     - Decision logic
     - ``ModelShadower`` runs primary in one greenlet and candidate in
       another; calls a ``ShadowEvaluator`` only when both succeed.

Model abstraction layer
=======================

The four abstraction files contain no transport code and no model-
specific knowledge. A new model is added by writing a new
``ModelEndpoint`` (the wire send) and pairing it with an existing
``InferenceModel`` subclass (the tokenize-and-send orchestrator).

``model.py`` — generic base classes
-----------------------------------

Despite the file name, ``model.py`` does **not** define a single
``Model`` class. It defines a layered set of generic abstractions
that the concrete clients compose:

* ``TokenizedInput[T]`` (dataclass) — the tokenization result. Holds
  ``original_input_text``, the (possibly truncated) ``input_text``,
  the ``tokens`` actually fed to the model, ``overflow_tokens`` that
  did not fit, and ``all_tokens`` for ratio computations. The
  ``overflow_ratio()`` method is what gets logged on every call.
* ``TokenizeOptions(max_tokens: Optional[int])`` — controls truncation.
* ``ModelTokenizer`` (ABC) with the concrete
  ``HFPretrainedModelTokenizer`` wrapping a HuggingFace
  ``PreTrainedTokenizerFast``. Exposes
  ``get_tokenized_input_as_int_list`` and
  ``get_tokenized_input_as_numpy_ndarray`` so endpoints can choose the
  shape that matches their wire format (the gRPC path needs
  ``np.ndarray``; the AI-Gateway path needs ``List[int]``).
  ``apply_model_chat_template[_tokenized]`` builds the chat-formatted
  prompt with HF's template engine.
* ``PreparedRequest[T]`` — a thin wrapper around the
  ``TokenizedInput[T]`` that ``ModelEndpoint.send`` consumes.
* ``ModelEndpoint[T, U, P]`` (ABC) with one abstract method
  ``send(prepared_request, parameters) -> U`` and an
  ``__init__(context_length: int)`` so callers can size their token
  budget. ``T`` is the wire-shape (``List[int]`` or ``np.ndarray``),
  ``U`` is the response object, ``P`` is endpoint parameters.
* ``ModelPromptTemplate`` — a Jinja2-backed wrapper that turns user
  text into the model-specific prompt envelope; takes the rendered
  string as ``content`` and ``markupsafe``-escapes it.
* ``InferenceResult[U]`` (dataclass) — what the top layer returns:
  ``model_response: U``, ``token_overflow_ratio: float``,
  ``consumed_tokens: int``. The overflow ratio and consumed tokens
  feed analytics; they are not used to gate the response.
* ``InferenceModel[U, P]`` — the public surface. Exposes one
  abstract method, ``run_inference(input: str, endpoint_parameters: P)
  -> InferenceResult[U]``. **There is no async variant** — the
  application is built on Flask + gevent, not asyncio.
* ``INPUT_TEMPLATE = Template("{{input}}", autoescape=True)`` — the
  *outer* escaping pass applied to user text before the prompt
  template renders. Both ``LlamaModel.run_inference`` and
  ``GPTOSSModelInTeamserve.run_inference`` start with
  ``input = INPUT_TEMPLATE.render(input=input)``.

Adding a new model means: pick a wire shape, subclass
``ModelEndpoint`` to produce the correct request, and reuse one of the
existing ``InferenceModel`` orchestrators
(``LlamaModel`` / ``LlamaModelInTeamserve`` / ``GPTOSSModelInTeamserve``)
or write a thin one. There is no central registry — wiring happens in
the per-model factory functions (``create_rai_llama_models`` etc.) and
by feature flags in the ``…Models.get_model()`` selectors.

``errors.py`` — minimal exception hierarchy
-------------------------------------------

The whole file is ~20 lines. Two classes:

* ``PromptModerationError(Exception)`` — base; no callers raise it
  directly today.
* ``MalformedModelOutput(PromptModerationError)`` — raised when a
  model response cannot be parsed: pydantic ``ValidationError`` from
  the AI-Gateway response, JSON parse failure from GPT-OSS chat
  output, or empty/short ``top_tokens`` lists from the Triton path
  (note: the last one currently *logs and falls back* to a default
  score rather than raising — see ``LlamaModel._get_score_from_details``).

The catch-all transport / status / circuit / timeout exceptions are
**not** re-classified into a custom hierarchy; they flow through to
``error_handling.py`` as the underlying library types
(``httpx.TimeoutException``, ``InferenceServerException``,
``pybreaker.CircuitBreakerError``, ``requests.exceptions.*``,
``AIGatewayResponseException``).

``error_handling.py`` — fail-open context manager
-------------------------------------------------

This module is **not** a retry decorator. It exposes one context
manager, ``inference_error_handler(ctx)``, plus a sibling dataclass
``InferenceErrorContext`` that the caller pre-populates with the
prompt/model versions and the feature service. Usage from
``service/moderation/prompt/prompt_moderation.py``::

   error_ctx = InferenceErrorContext(prompt_evaluation_version=…,
                                     model_evaluation_version=…,
                                     feature_service=feature_service)
   with inference_error_handler(error_ctx):
       response = model.run_inference(prompt, params)
       …
   if error_ctx.did_fail_open:
       fo = error_ctx.fail_open_result
       return PredictionResult(prompt_harm_category=NONE,
                               violation_score=fo.violation_score, …)

Behaviour, by exception type, is summarised below. Each row is one
``except`` clause / handler in ``error_handling.py``.

.. list-table:: ``inference_error_handler`` exception map
   :header-rows: 1
   :widths: 40 30 30

   * - Caught exception
     - Behaviour
     - Source
   * - ``InferenceServerException`` whose message *does not* contain
       ``"Deadline Exceeded"``
     - Re-raised as ``APIException(500)``
     - ``_handle_timeout_or_inference_error``
   * - ``InferenceServerException`` containing ``"Deadline Exceeded"``,
       or ``httpx.TimeoutException``
     - **Fail open** (violation_score=0.5) iff
       ``feature_service.should_fail_open_on_model_timeout()``;
       otherwise ``APIException(504)``
     - same handler
   * - ``httpx.TransportError``
     - ``APIException(503)``
     - ``_handle_transport_error``
   * - ``pybreaker.CircuitBreakerError``
     - **Fail open** (violation_score=0.0) iff
       ``feature_service.should_fail_open_if_circuit_breaker_open()``;
       otherwise ``APIException(503)``
     - ``_handle_circuit_breaker_error``
   * - ``requests.exceptions.Timeout``
     - **Fail open** (violation_score=0.5) iff the same
       timeout-fail-open flag is on; otherwise ``APIException(504)``
     - ``_handle_requests_timeout``
   * - ``requests.exceptions.HTTPError``
     - Re-raised as ``APIException`` with the upstream status code
     - ``_handle_requests_http_error``
   * - ``requests.exceptions.ConnectionError``
     - ``APIException(503)``
     - ``_handle_requests_connection_error``
   * - ``MalformedModelOutput``
     - **Fail open** (violation_score=0.0); always — no flag gate
     - ``_handle_malformed_output``
   * - ``AIGatewayResponseException``
     - ``APIException.from_ai_gateway_error(exc)``
     - ``_handle_ai_gateway_error``

Two non-obvious points:

* **The fail-open default is asymmetric.** Timeouts pick ``0.5`` (the
  middle of the score range, paired with ``PromptHarmCategory.NONE``
  in the caller) so that downstream uncertainty thresholds can still
  flag genuine timeouts. Circuit-breaker and malformed-output failures
  pick ``0.0`` because they indicate the model is unreachable or
  generated garbage — failing open conservatively means "treat as
  safe."
* **No retries here.** Retries on the AI Gateway path are configured at
  the SDK level in
  ``api/v1/moderation/app_context.py:custom_retry_config``: 2 attempts,
  ``wait_random_exponential(multiplier=1, min=0.5, max=1.5)``,
  retrying only on ``httpx.TimeoutException`` /
  ``httpx.NetworkError`` (HTTP 429 is **not** retried). That retry
  config is opt-in via ``feature_service.is_custom_retry_config_enabled()``.

The handler is currently used **only** by the prompt-moderation path.
The image path catches its own gevent greenlet errors in
``ImageModerationSageMaker._extract_greenlet_result``.

``image_moderation_types.py`` — image constants and pydantic shapes
-------------------------------------------------------------------

A 30-line module with module-level constants and three pydantic
models. The full contents:

* ``HUMAN_CLASS_ID = 0`` — class id used when scanning V0 detector
  outputs for the (legacy) "human" violation category.
* ``MODERATION_THRESHOLD = 0.4`` — exported but **not** used by any
  V0 / V1 score computation in the package today; kept for callers
  that need a default.
* ``ImageModerationOutputV0(labels, boxes, scores)`` — V0 detector
  output shape. ``labels`` is ``List[List[int]]`` (per-batch label
  lists), ``scores`` matches.
* ``ImageModerationOutputV1(policy: str, prediction: dict[str, float])``
  — ShieldGemma's response. The score lives at
  ``prediction["Unsafe"]``.
* ``ResponseAIImageResponse(category, to_be_filtered, violation_score,
  model_evaluation_version="v0")`` — the unified return shape that
  ``image_moderation_sagemaker.py`` builds from either V0 or V1
  output.

There is no ``ImageModerationRequest``: callers pass the base64
image bytes as a plain ``str`` to ``run_inference``.

Concrete model clients
======================

Each section below lists one client's invocation path, request /
response shape, score derivation, and where its errors are mapped.

``rai_llama.py`` — the Llama family
-----------------------------------

The file ships **three** model variants and a feature-flag-driven
selector that is the closest thing the package has to a router.

**The three variants**, all producing ``ResponseAIResponse``:

#. ``V2_3_3_prompt_v2`` — built as
   ``LlamaModel(llama_tokenizer, RAIFTEndpointV2_3_3, prompt_v2_template, …)``.
   Transport: AI Gateway via ``msp_sdk.invoke_rai_ft_2_3_3``
   (``ResponsibleAIFineTunedModelRequest`` → JSON over HTTP). This is
   *not* a Triton path. The model is asked for ``top_n_tokens=2``
   so the client can compute a probability over the
   ``true``/``false`` token at position 5.
#. ``V2_3_3_teamserve`` — built as
   ``LlamaModelInTeamserve(llama_tokenizer, RAIFTTeamserveEndpoint(teamserve_endpoint, …, v2_3_3_ts_plugin), …)``.
   Transport: Triton gRPC. The ``TeamservePlugin`` injects
   ``x-teamserve-model: teamserve-rai-v2-3-989307885653997``,
   ``x-teamserve-source: teamserve``, and an ASAP JWT.
#. ``V2_4_teamserve`` — same as above but with the V2_4 plugin
   (``rai-v2-4-llama3-1-8b-1049``) and the V2_4 prompt template.

Both Teamserve variants point at the **same** Triton model name,
``teamserve-rai-optimized-logits``, version ``"1"`` — versioning is
done in the Teamserve routing layer above Triton via the plugin
headers, not at the Triton model level. (See ``RAIFTTeamserveEndpoint.__init__``
in ``rai_llama.py`` and ``GrpcEndpoint`` construction in
``triton_grpc_client.py``.)

**Selector and shadowing.** ``RAILlamaModels.get_model()`` picks the
primary in this order::

   if feature_service.is_prompt_moderation_teamserve_v2_4_primary_enabled():
       primary = V2_4_teamserve
   elif feature_service.is_rai_ft_teamserve_primary_enabled():
       primary = V2_3_3_teamserve
   else:
       primary = V2_3_3_prompt_v2

Then optionally wraps the primary in a ``ShadowShim`` if the matching
shadow flag is on:
``is_shadow_with_teamserve_v2_4_enabled``,
``is_rai_ft_teamserve_shadowing_enabled``, or
``is_shadow_with_ai_gateway_2_3_3_enabled``. The selector returns a
``SelectedModel(version, model)`` whose ``version`` field is what
ends up in the prompt/model evaluation version on the response.
Shadowing is **not** a fallback; if the shim is in place it always
fires (subject to the gevent pool-full guard, see
`Model shadowing`_).

**Triton gRPC invocation path** (``LlamaModelInTeamserve`` →
``RAIFTTeamserveEndpoint`` → ``GrpcEndpoint``):

#. Caller passes ``input: str`` and ``endpoint_parameters:
   RAIFTEndpointParameters(http_headers={…})``.
#. ``run_inference`` renders ``INPUT_TEMPLATE`` over the user text,
   computes a ``TokenizeOptions(max_tokens=…)`` budget that subtracts
   the chat template + a 10-token (or 1000-token, under
   ``is_increased_input_clipping_buffer_enabled``) buffer from the
   model's ``TOKENIZED_CONTEXT_LENGTH = 15900``, tokenizes as numpy
   ndarray, and asserts non-zero length when
   ``is_strict_tokenization_failure_enabled`` is on (otherwise just
   logs).
#. ``_prepare_request`` re-renders the prompt envelope, applies the
   HF chat template (system prompt + user prompt), re-tokenizes the
   final string, and wraps it as a ``PreparedRequest``.
#. ``RAIFTTeamserveEndpoint.send`` reshapes ``input_ids`` to
   ``[batch, seq_len]`` if needed, builds ``input_lengths``,
   sets ``request_output_len = 21`` (per batch), and calls
   ``self.client.invoke(input_ids=…, input_lengths=…,
   end_id=3934, request_output_len=…, temperature=0.0)``.
   ``end_id=3934`` is the tokenizer id for the literal ``"false"`` —
   inference stops as soon as that token would be generated.
#. ``GrpcEndpoint.invoke`` adds two boolean inputs unconditionally —
   ``return_generation_logits=True`` and ``return_log_probs=True`` —
   wraps the call in
   ``self.breaker.calling()`` (the per-class
   ``CircuitBreaker(fail_max=30)``), and asks for outputs
   ``output_tokens`` and ``log_probs``. Server timeout is
   ``5_000_000`` (microseconds in Triton's gRPC client; the literal
   string in the comment is "5 seconds"); ``client_timeout=6``.
#. ``RAIFTTeamserveEndpoint.send`` then reads ``log_probs`` at
   position ``5``, applies ``scipy.special.softmax``, and pulls the
   probability at index ``[0]`` as the ``violation_score``. The
   ``output_ids`` are decoded with the tokenizer
   (``skip_special_tokens=True``) and parsed as
   ``PromptModerationGeneratedText`` — pydantic ``ValidationError``
   here becomes ``MalformedModelOutput``.

**AI Gateway invocation path** (``LlamaModel`` →
``RAIFTEndpointV2_3_3``):

#. Same tokenization scaffolding.
#. ``RAIFTEndpointV2_3_3._try_send`` calls
   ``msp_sdk.invoke_rai_ft_2_3_3`` (which the SDK retries via
   tenacity, see :ref:`config-overview`), gets a
   ``ResponsibleAIFineTunedModelResponse``, raises
   ``MalformedModelOutput`` on pydantic ``ValidationError``.
#. ``LlamaModel._get_score_from_details`` derives the violation score
   from ``details.top_tokens[5]``: softmax over the ``logprob`` of
   the top-2 tokens, then if the top token (lowercased and stripped)
   is ``"true"`` the violation probability is ``top_prob``; if
   ``"false"``, it is ``1 - top_prob``; otherwise it logs and
   defaults to ``0.5``. Same default applies if ``top_tokens`` is
   empty or shorter than expected.

**Request / response schema**, summarized:

* gRPC request named tensors (always present):
  ``input_ids`` ``INT32 [B, seq_len]``,
  ``input_lengths`` ``INT32 [B, 1]``,
  ``request_output_len`` ``INT32 [B, 1] = 21``,
  ``return_generation_logits`` ``BOOL [B, 1] = True``,
  ``return_log_probs`` ``BOOL [B, 1] = True``,
  plus optional scalars (``temperature``, ``end_id``).
* gRPC response named tensors: ``output_tokens``, ``log_probs``.
* AI-Gateway request body: ``ResponsibleAIFineTunedModelRequest(inputs=…,
  parameters=ResponsibleAIFineTunedModelParametersRequest(do_sample=False,
  return_full_text=False, details=True, top_n_tokens=2))``.
* Top-layer return: ``ResponseAIResponse(category, toBeFiltered,
  violation_score)`` wrapped in
  ``InferenceResult(model_response, token_overflow_ratio,
  consumed_tokens)``.

**Confidence threshold logic.** ``rai_llama.py`` itself does
**not** apply thresholds. The score reaches the caller as a raw
float; the caller (``PromptModerationService``, see
:ref:`svc-moderation`) calls
``confidence.get_prompt_harm_category_confidence_threshold[_by_model_version](harm_category,
tenant_id[, model_evaluation_version])`` and applies
``threshold.exceeds_threshold(score)``. The model version that goes
into that lookup is the ``version`` field set by
``RAILlamaModels.get_model()`` (e.g.
``"V2_3_3_teamserve"``, ``"V2_4_teamserve"``, or shimmed
``"V2_4_teamserve_shimmed_V2_3_3_teamserve"``).

**Error taxonomy.** Triton ``InferenceServerException`` with a
"Deadline Exceeded" message and ``httpx.TimeoutException`` map to
fail-open or 504 (see `error_handling.py — fail-open context manager`_).
Other ``InferenceServerException`` map to 500. AI-Gateway responses
that fail pydantic validation become ``MalformedModelOutput`` →
fail-open with ``violation_score=0.0``. Tokenizer errors
(loaded once at factory time) raise immediately and prevent the
service from booting — no per-request fallback path exists for a
broken tokenizer.

``rai_gpt_oss.py`` — GPT-OSS Safeguard 20b
------------------------------------------

A single ``InferenceModel`` (``GPTOSSModelInTeamserve``) wired to a
single ``ModelEndpoint`` (``RAIFTTeamserveEndpoint``, defined inside
this file — distinct from the same-named class in ``rai_llama.py``)
that talks to Triton's OpenAI-compatible HTTP path. The factory is
``create_rai_gpt_oss_models``; the selector
``RAIGPTOSSModels.get_model()`` always returns
``SelectedModel(version="gpt_oss_safeguard_20b",
model=self.gpt_oss_safeguard)`` — there is no shadow chain on this
side today.

**Invocation path:**

#. ``run_inference`` mirrors the Llama path: render
   ``INPUT_TEMPLATE`` → compute token budget against
   ``TOKENIZED_CONTEXT_LENGTH = 15900`` minus the chat-template
   length and the ``buffer_size``; tokenize as ``int_list``; assert
   non-empty when ``is_strict_tokenization_failure_enabled``.
#. ``_prepare_request`` does **not** apply the HF chat template
   locally — the comment in the file makes this explicit:
   "the Teamserve HTTP endpoint (OpenAI-compatible) handles the chat
   template server-side. The system prompt is stored on
   ``RAIFTTeamserveEndpoint`` and injected at send time." The local
   tokenizer is therefore used only to compute the input-budget
   token count and the truncated ``input_text`` that goes into the
   user message.
#. ``RAIFTTeamserveEndpoint.send`` builds
   ``messages = [{"role": "system", …}, {"role": "user", …}]`` and
   calls
   ``self.client.send_chat_completions(messages=messages,
   reasoning_effort="low", temperature=0.0, max_tokens=400)``.
#. ``TritonOpenAIClient.send_chat_completions`` POSTs the JSON body
   to ``url`` (configured by the caller — ``teamserve_gptoss_endpoint``
   from app context) with ``timeout=6`` seconds, the ``Authorization``
   header injected by ``atlassian_jwt_auth``'s ``JWTAuth(asap_signer,
   audience="teamserve")``, wrapped in a
   ``CircuitBreaker(fail_max=30)`` that shares the *name*
   ``"triton_circuit_breaker"`` with the gRPC client (note: each
   ``GrpcEndpoint`` / ``TritonOpenAIClient`` instance has its own
   breaker instance — the shared name is for telemetry, not state).
#. The endpoint extracts ``response_json["choices"][0]["message"]["content"]``,
   raises ``MalformedModelOutput`` if it's ``None``.
#. **JSON parsing is defensive.** The model often emits reasoning
   text before the JSON verdict, so the client takes
   ``content[content.rfind("{", 0, content.rfind("}")+1) :
   content.rfind("}")+1]`` (the *last* ``{...}`` block). On
   ``json.JSONDecodeError`` the client normalizes — replaces ``'``
   with ``"`` and rewrites ``True``/``False`` to ``true``/``false`` —
   then retries the parse once. A second failure becomes
   ``MalformedModelOutput``. Pydantic validation failure on the
   parsed dict is the same.
#. **Score derivation is binary.** The OpenAI-compatible HTTP path
   does not return token-level logprobs, so the endpoint sets
   ``violation_score = 1.0 if generated_text.toBeFiltered else 0.0``.
   This is the single most important practical difference from the
   Llama gRPC path and explains why this transport was chosen for a
   model used as a "second opinion" rather than as the only
   classifier (see `Why two Triton client variants exist`_).

**Confidence threshold logic.** Same external mechanism as the
Llama path — applied by ``PromptModerationService``, not by the
model client. With a binary score the threshold is effectively a
gate on ``toBeFiltered`` (any non-zero default threshold of ``0.5``
admits ``1.0`` and rejects ``0.0``).

**Error taxonomy.** ``requests.exceptions.Timeout`` /
``HTTPError`` / ``ConnectionError`` are caught by
``inference_error_handler`` (the ``GPT-OSS teamserve`` log lines in
the handler are specifically for this path). ``MalformedModelOutput``
fails open at ``violation_score=0.0``.

``image_moderation_sagemaker.py`` — image classifier on SageMaker
-----------------------------------------------------------------

The file hosts **two** clients and a parallel-execution policy that
is more elaborate than its sibling text models.

* ``ImageModerationSageMaker(SageMakerInferenceBase)`` — the V0
  detector. Endpoint name is the constructor argument
  (``config.sm_endpoint_image_moderation`` from app context). On
  construction it also reads ``config.sm_endpoint_image_moderation_v1``
  and instantiates ``ImageModerationV1Client(v1_endpoint, …)``;
  missing V1 config raises ``ValueError`` at app start. It owns a
  shared ``gevent.pool.Pool(size=config.inference_pool_size)`` for the
  parallel V0/V1 path.
* ``ImageModerationV1Client(SageMakerInferenceBase)`` — ShieldGemma.

**Invocation path** (``run_inference(image_data: str)``):

#. If
   ``feature_service.is_image_moderation_v1_enabled() and
   feature_service.is_use_case_allowed()`` →
   ``_run_parallel_inference``. Otherwise →
   ``_run_v0_inference`` only.
#. **Parallel path:**

   * If ``self.inference_pool.full()`` → ``_handle_pool_full_fallback``
     runs V0 only; if V0 doesn't return a
     ``ResponseAIImageResponse`` the safe default is returned. This
     is a load-shedding guard, not an error path.
   * Otherwise spawn two greenlets (V0 and V1), copy
     ``contextvars`` so OpenTelemetry spans propagate, and
     ``joinall([…], timeout=config.greenlet_join_timeout)``.
   * Greenlets that did not finish in time count as ``num_timed_out``;
     greenlet exceptions are extracted via
     ``_extract_greenlet_result``. If both errored → raise
     ``ValueError`` (which propagates out of the layer; the image
     path does **not** use ``inference_error_handler``).
   * ``_merge_detection_results`` returns the V1 response if V1
     detected a violation (``to_be_filtered`` or any non-NONE
     ``category``); otherwise it returns V0. After merging, if
     nothing was flagged but at least one model timed out, the
     method raises ``ValueError("N model(s) timed out")`` — i.e.
     timeouts are tolerated only if the side that finished said
     "violation."

**Score derivation:**

* V0: ``_calculate_v0_violation_score`` walks all
  ``(label, score)`` pairs in
  ``ImageModerationOutputV0`` and takes the *max* score whose label
  equals ``HUMAN_CLASS_ID = 0``. If
  ``feature_service.is_standardized_image_moderation_response_enabled``
  is on, the score is gated against
  ``config.image_moderation_v0_threshold`` to produce
  ``to_be_filtered`` and ``category = ImageHarmCategory.HUMAN`` /
  ``NONE``. Otherwise the raw ``ImageModerationOutputV0`` is returned
  (and the caller flattens it).
* V1: ``_convert_v1_to_standard_response`` reads
  ``v1_output.prediction["Unsafe"]`` (defaulting to ``0.0``),
  compares against ``config.image_moderation_v1_threshold``,
  builds a ``ResponseAIImageResponse`` whose category comes from
  ``ImageHarmCategory(v1_output.policy)`` when the score crosses
  the threshold, ``NONE`` otherwise.

The "highest score wins" rule for ShieldGemma sits in
``parse_v1_response_with_highest_score`` — when the V1 endpoint
returns a list of policy predictions, the client picks the entry
with the largest ``prediction["Unsafe"]`` and ignores the rest.

**Confidence threshold logic.** Image thresholds are read from
``config.image_moderation_v0_threshold`` / ``image_moderation_v1_threshold``
(static config), **not** from ``confidence/confidence_thresholds.py``.
The ``confidence/`` subpackage is exclusively the *prompt* threshold
path. This is a real seam — image and prompt threshold sources are
separate and the package does not unify them.

**Error taxonomy.** ``ClientError`` from boto3 in the V1 client is
re-logged and re-raised. ``KeyError`` /
``TypeError`` / ``json.JSONDecodeError`` from V0 response parsing are
re-raised as ``ValueError``. Any greenlet exception is captured and
surfaces in the per-greenlet result extraction.

``sagemaker_base.py`` — boto3 invocation primitives
---------------------------------------------------

A small ABC for the SageMaker-hosted clients. Three responsibilities:

* **Lazy boto3 client construction** in ``_create_runtime_client``
  with a fallback chain: default credentials →
  on ``NoCredentialsError`` /
  ``ClientError`` / ``BotoCoreError``, try ``sts.assume_role`` on
  ``arn:aws:iam::540824312222:role/SageMakerExecutionRole`` →
  on a second failure, fall back to default credentials anyway. The
  hard-coded role ARN is the only bit of AWS account information in
  the package and matches the production deployment account.
* **``invoke_sagemaker_endpoint(payload)``** — calls
  ``self.runtime.invoke_endpoint(EndpointName=self.endpoint,
  ContentType="application/json", Body=json.dumps(payload))``.
  Both V0 and V1 clients send ``{"image": image_data}`` as the
  payload — there is no separate dispatch shape.
* **``parse_json_response(response)``** — decodes
  ``response["Body"].read().decode()`` as JSON. If the result is a
  list it returns ``result[0]``; if a dict, it returns the dict;
  anything else raises ``ValueError("Unexpected response format
  from SageMaker endpoint")``.

The base class does **not** own retry, timeout, or connection-pool
configuration. boto3 defaults apply. There is no
``ContentType``/``Accept`` parameterization.

Wire-protocol clients
=====================

``triton_grpc_client.py``
-------------------------

Two classes:

* ``TeamservePlugin(InferenceServerClientPlugin)`` — set on the
  ``InferenceServerClient`` once at construction time. On every
  request it injects four headers:
  ``x-teamserve-model``, ``x-teamserve-model-version``,
  ``x-teamserve-source``, and
  ``authorization: Bearer <ASAP JWT>`` (signed by an
  ``atlassian_jwt_auth.signer.JWTAuthSigner`` with audience
  ``"teamserve"``). The plugin is *the* mechanism that routes a
  single Triton model name (``teamserve-rai-optimized-logits``) to
  one of several Teamserve-side variants (``rai-v2-3-…`` or
  ``rai-v2-4-…``).
* ``GrpcEndpoint`` — owns the ``InferenceServerClient(url=…,
  ssl=True, verbose=False)`` (``tritonclient.grpc``), the plugin, the
  Triton model name and version, and a per-instance
  ``pybreaker.CircuitBreaker(name="triton_circuit_breaker", fail_max=30)``.
  ``invoke(input_ids, input_lengths, request_output_len, **kwargs)``
  builds the input list (always including the two boolean
  ``return_*`` flags), packs each kwarg into a ``[batch, 1]`` array
  with a runtime dtype check (``bool`` → ``BOOL``, ``int`` →
  ``INT32``, ``float`` → ``FP32``, anything else → ``STRING``),
  requests outputs ``output_tokens`` and ``log_probs``, and calls
  ``triton_client.infer(…, timeout=5*1000*1000, client_timeout=6)``
  inside ``self.breaker.calling()``. Returns
  ``{"output_ids": result.as_numpy("output_tokens"),
  "output_log_probs": result.as_numpy("log_probs")}``.

``is_healthy()`` — exposed for readiness checks — returns
``True`` when the circuit-breaker state is **not** ``"open"`` (i.e.
``"closed"`` or ``"half-open"``). It is only called from health-check
code paths outside this file; nothing in ``inference_models/`` calls it.

``triton_openai_api_client.py``
-------------------------------

A 30-line client. ``TritonOpenAIClient(url, asap_signer, audience="teamserve")``
holds:

* ``self.url`` — the chat-completions endpoint (caller-provided;
  ``config.teamserve_gptoss_endpoint`` in production).
* ``self.auth = JWTAuth(asap_signer, audience)`` — a
  ``requests``-compatible auth that signs each request with an ASAP
  JWT.
* ``self.headers = {"Content-Type": "application/json"}``.
* ``self.breaker = pybreaker.CircuitBreaker(name="triton_circuit_breaker", fail_max=30)``.

``send_chat_completions(messages, **kwargs) -> dict`` builds
``{"messages": messages, **kwargs}``, posts with ``timeout=6``,
calls ``response.raise_for_status()`` (so HTTP errors propagate as
``requests.exceptions.HTTPError``), and returns ``response.json()``.
There is no streaming variant. There is no per-attempt timeout
configuration beyond the literal ``6`` seconds.

gRPC vs OpenAI-compatible HTTP — at a glance
--------------------------------------------

.. list-table:: Transport choice per model
   :header-rows: 1
   :widths: 35 25 40

   * - Model
     - Transport
     - Why
   * - ``V2_3_3_prompt_v2`` Llama
     - AI Gateway (``msp_sdk.invoke_rai_ft_2_3_3``)
     - Pre-existing route through the AI-Gateway TGI path; returns
       ``details.top_tokens`` so a probability over the
       ``true``/``false`` token at position 5 is computable.
   * - ``V2_3_3_teamserve`` / ``V2_4_teamserve`` Llama
     - Triton gRPC
     - Returns ``log_probs`` for arbitrary positions; the violation
       score is derived from ``softmax(log_probs[5])[0]``. The
       binary tensor wire format is materially smaller than JSON for
       the dense ``input_ids`` array, and Triton's gRPC path
       supports the named-tensor schema needed for the custom
       Teamserve model. The ASAP token + Teamserve headers are
       injected by ``TeamservePlugin``.
   * - GPT-OSS Safeguard 20b
     - Triton OpenAI-compatible HTTP (``/v1/chat/completions``)
     - GPT-OSS is a generative classifier whose prompt is a chat
       template applied **server-side**; sending a plain
       ``messages`` array is the natural shape and matches the
       offline evaluation harness. The OpenAI path does not return
       token-level logprobs, so the score is forced to be binary —
       acceptable today because GPT-OSS is feature-flagged behind
       ``is_gpt_oss_safeguard_enabled`` and is not the primary
       classifier.
   * - Image classifier (V0 + V1)
     - SageMaker ``invoke_endpoint`` via boto3
     - Hosted on SageMaker historically; not Triton.

Confidence subpackage
=====================

``confidence/`` contains exactly one source file
(``confidence_thresholds.py``) plus a re-exporting ``__init__.py``.
There is **no** calibration module — score calibration, where it
exists at all, is part of the offline model-training pipeline and
not represented in code under ``inference_models/``.

What it offers
--------------

* ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5`` — used whenever the
  category is missing from config, the parse fails, or the dynamic
  config lookup returns nothing.
* ``PromptHarmConfidenceThreshold(harm_category, threshold)`` — a
  single (category, threshold) pair. ``exceeds_threshold(score)``
  validates ``score`` is in ``[0, 1]`` (raises ``ValueError`` if not)
  and returns ``score >= threshold``. So **the threshold is
  inclusive on the upper boundary** — an exact-equal score crosses
  it.
* ``PromptHarmConfidenceThresholds`` — a collection keyed by
  ``PromptHarmCategory``. ``get_threshold(harm_category)`` returns
  a ``PromptHarmConfidenceThreshold(category, 0.5)`` when the
  category is not present rather than raising.
* Two parsers: a flat ``"slug:threshold"`` string list (legacy) and a
  nested JSON keyed by model evaluation version with a fallback
  ``"other"`` key (newer).

Source of truth and lookup
--------------------------

* The flat thresholds live in dynamic config under
  ``responsible-ai-api-prompt-harm-thresholds``.
* The per-version thresholds live in
  ``responsible-ai-api-prompt-thresholds-by-version`` as a JSON map
  ``{ version_or_other: { slug: threshold } }``. Lookup tries the
  exact ``model_evaluation_version``, then the literal ``"other"``,
  then raises.
* All lookups go through Atlassian dynamic config
  (``atlassian_dynamic_config_sdk.client.Identifiers(tenantId=tenant_id)``),
  i.e. **per-tenant**. There is no global threshold.
* Both lookup functions are wrapped in
  ``@time_cache(max_age=60)`` from ``src.cache`` — values may be up
  to one minute stale per tenant. There is no startup-time
  pre-load.
* Every parse / fetch failure logs and falls back to
  ``PromptHarmConfidenceThresholds.default()`` (i.e. the empty
  dict, so every category resolves to ``DEFAULT_CONFIDENCE_THRESHOLD``).
  The package never raises out of a threshold lookup once the
  fallback path has executed.

What the thresholds gate
------------------------

The thresholds gate the *user-visible verdict*, not the model
invocation. The model produces a raw score; the caller in
``svc-moderation`` looks up the threshold for
``(tenant, harm_category[, model_version])`` and decides whether the
prediction is "filtered." The model layer never short-circuits a
call because of a threshold.

Calibration
-----------

Not represented in this package. The threshold values themselves
are the only calibration artifact, and they are tuned offline and
delivered via dynamic config. There is no client-side rescaling of
self-reported scores (the existing GPT-OSS binary score is the most
extreme illustration: there's nothing to calibrate against).

Model shadowing
===============

``model_shadowing/`` is a small subpackage (``shadower.py`` plus an
empty ``__init__.py``) that runs a candidate model alongside the
primary so engineers can compare them on real production traffic
without affecting the user-visible response.

Shape and behaviour
-------------------

* ``ShadowEvaluator[A, B]`` (ABC) — one method,
  ``evaluate(model_a_result, model_b_result)``. The package ships
  exactly one implementation,
  ``RAIModelShadowEvaluator`` in ``rai_llama.py``: it ``logger.info``-s
  a structured diff line ``(category_a vs category_b, toBeFiltered_a
  vs toBeFiltered_b, violation_score_a vs violation_score_b, abs
  diff)``. Comparison output goes to logs only — there is no
  Kafka/S3/analytics emission today.
* ``ModelShadower[U, P]`` — owns a ``gevent.pool.Pool(20)``
  (``DEFAULT_MAX_POOL_SIZE = 20``). ``run_inference(input, params,
  model_a, model_b)`` does:

  #. If the pool is full → run primary only and skip shadowing
     (logged at ``warning``). The primary's response is returned;
     no greenlet is spawned for the shadow.
  #. Spawn ``greenlet_a`` (primary).
  #. Spawn ``greenlet_b = pool.spawn(wait_for_b)`` where
     ``wait_for_b`` runs the candidate, then if the evaluator is
     present *waits up to 5 seconds* for ``greenlet_a`` to finish,
     and calls ``evaluator.evaluate(a, b)`` only if both succeeded.
  #. Both greenlets get ``contextvars.copy_context()`` so OpenTelemetry
     and request-context propagate.
  #. Returns ``greenlet_a.get()`` synchronously — so the user-visible
     response is bound to the primary's latency, not the shadow's.

* ``ShadowShim[U, P](InferenceModel[U, P])`` — wraps two
  ``InferenceModel`` instances so the shimmed object satisfies the
  same interface as either model. ``run_inference`` delegates to
  ``ModelShadower.run_inference``. This is what
  ``RAILlamaModels.get_model()`` returns when a shadow flag is on.

How sampling works
------------------

There is **no per-request sampler** inside ``shadower.py``. The
sampling decision is made one level up by the feature flags
evaluated in ``RAILlamaModels.get_model()``:

* When the relevant ``is_shadow_with_…`` flag is **on** every
  request through the prompt path goes through the shim — i.e. it
  is "100% shadow" for the matching tenant scope.
* When the flag is off the shim is not constructed and the primary
  is returned directly.

The only in-package mechanism that backs off shadowing is the
gevent pool-full guard (which silently drops to primary-only). This
is the load-shedding behaviour and it is the right one — engineers
should not reach for a per-request sample rate inside
``model_shadowing/``; if traffic-percentage shadowing is needed,
the right place is the feature flag, not this module.

How shadow vs primary is compared
---------------------------------

* The comparator is plug-in: ``ShadowEvaluator.evaluate``. The Llama
  evaluator (``RAIModelShadowEvaluator``) compares the two
  ``InferenceResult[ResponseAIResponse]`` objects on three fields
  — ``category``, ``toBeFiltered``, ``violation_score`` — and logs
  the absolute score delta as ``%.4f``.
* The comparator runs only when both greenlets succeeded **and**
  the primary finished within the 5-second wait inside
  ``wait_for_b``. If the primary takes longer the comparator is
  skipped (logged), but the primary's response is still returned to
  the caller (the outer ``greenlet_a.get()`` does not have a
  timeout — production latency for primary is not bounded by the
  shadower's evaluator deadline).
* All shadow failures are swallowed: ``Model B failed. Skipping
  evaluation.`` (``logging.error`` with ``exc_info``). A broken
  candidate model never affects the user-visible response and never
  escapes the layer.

Where shadow output goes
------------------------

It goes to logs. Every shadowed call produces a single structured
``logger.info`` line in ``rai_llama.py``'s
``RAIModelShadowEvaluator`` containing both responses' fields plus
the score delta. Aggregation and analysis happen in the log
pipeline (Splunk / similar), not in this package. Critically, the
emitted line does *not* include the original prompt text — the
``run_inference`` argument is consumed by both models but the
evaluator only sees the responses. Re-identifying inputs requires
correlating timestamps / request IDs against the upstream service's
own access logs, which is a deliberate privacy boundary inherited
from the moderation service's logging policy.

Tokenizers
==========

Tokenizer assets live at the **project root** under ``tokenizers/``,
not under ``src/inference_models/``. This is a deliberate placement
so the directories are bundled with the deployment image but not
imported as Python.

.. list-table:: Tokenizer pairing
   :header-rows: 1
   :widths: 30 35 35

   * - Asset directory
     - Used by
     - Notes
   * - ``tokenizers/rai_ft_v2_1/``
     - **Not used by current code paths.**
     - The directory is present (``tokenizer.json``,
       ``tokenizer_config.json``, ``special_tokens_map.json``) but
       no factory loads it. Likely retained for offline tooling /
       backward-compatibility reasons; do not delete without
       confirming with model engineering.
   * - ``tokenizers/rai_ft_v2_2/``
     - ``rai_llama.py`` — both ``V2_3_3_*`` *and* ``V2_4_teamserve``
       use the **same** tokenizer.
     - Loaded once per process in ``create_rai_llama_models`` as
       ``llama_tokenizer = HFPretrainedModelTokenizer(PreTrainedTokenizerFast.from_pretrained("tokenizers/rai_ft_v2_2"))``.
       V2_3 and V2_4 share the vocabulary, so the asset is reused;
       the tokenizer object is shared by reference across all three
       Llama variants.
   * - ``tokenizers/gpt_oss_safeguard_20b/``
     - ``rai_gpt_oss.py``
     - Loaded in ``create_rai_gpt_oss_models`` via
       ``AutoTokenizer.from_pretrained("tokenizers/gpt_oss_safeguard_20b")``.
       Includes a substantial ``chat_template.jinja`` (~16 KB) that
       HF reads during construction — but the chat template is
       **not** applied locally for the production path; the OpenAI
       HTTP endpoint applies it server-side. The local tokenizer is
       used only for token budgeting in ``_tokenization_options``.

Loading at startup
------------------

Each factory function loads its tokenizer once with
``…AutoTokenizer / PreTrainedTokenizerFast.from_pretrained``. Both
factories are called from
``api/v1/moderation/app_context.get_prompt_moderation_service``, which
is itself called once per process to construct the
``PromptModerationService`` — so the tokenizers are loaded on first
service instantiation, not on import. Failure to load
(``OSError``, missing file, etc.) propagates out of the factory
and out of the service constructor; in deployment this surfaces as
a Flask startup failure rather than a per-request error.

Working-directory dependency
----------------------------

``from_pretrained("tokenizers/rai_ft_v2_2")`` is a **relative path**.
It assumes the gunicorn/Flask process is launched from the project
root (which it is, in production and in
``./bin/start-app-locally.sh``; see :ref:`architecture`). A
working-directory mismatch silently fails at startup and is
diagnosable from the boot logs.

Non-obvious decisions
=====================

A few choices in this layer are not self-explanatory from the code.
They are recorded here so future readers do not undo them.

Why two Triton client variants exist
------------------------------------

The package ships both a gRPC client and an OpenAI-compatible HTTP
client. The trade-off is *not* generic gRPC-vs-HTTP performance —
it is **what the model returns**:

* The Llama Teamserve path (``teamserve-rai-optimized-logits``)
  exposes ``log_probs`` for arbitrary token positions. The
  violation score is derived from ``softmax(log_probs[5])[0]``;
  position 5 is where the ``true``/``false`` decision token lives
  in the prompt template. Without per-position logprobs there is
  no continuous score.
* The GPT-OSS Safeguard path is exposed through Triton's
  OpenAI-compatible HTTP front-end, which speaks
  ``/v1/chat/completions`` and *does not* return per-token
  logprobs in this configuration. The chat-template application
  also happens server-side, which makes the client trivial — but
  it forces ``violation_score`` to be binary
  (``1.0 if toBeFiltered else 0.0``).

Picking only the gRPC client would force the GPT-OSS path to
re-implement the chat template locally and bypass the standard
OpenAI shape — which is also the shape the offline harness uses.
Picking only the HTTP client would make the Llama violation score
binary, eliminating the uncertainty signal that the
``confidence/`` thresholds gate against. Two clients is the cheaper
answer; the cost is that the two transports do not share circuit-
breaker state (they share the breaker *name* but each
``GrpcEndpoint`` / ``TritonOpenAIClient`` instance has its own
``CircuitBreaker``).

Why ``model_shadowing`` exists
------------------------------

Three reasons:

#. Offline evaluation drifts away from production traffic. A new
   Llama checkpoint that scores well on the offline reference set
   may regress on a category where production traffic has shifted.
#. Promoting a model fully ("primary" feature flag on, no shadow)
   without a comparable signal from real traffic is a cliff: the
   first regression page is the first signal.
#. Running the candidate against full traffic via a separate
   deployment is expensive and adds privacy surface.

The shim solution sits between these: per-request *both* models
run, the candidate's result is logged not used, the user-visible
response is unchanged, and the load goes through the same gunicorn
process so capacity-planning is the same as for primary-only.

The trade-off: shadow runs use the candidate's full per-request
budget (no budget separation), and the shadow's runtime errors are
silently swallowed. Both are intentional — capacity-planning under
"shadow on" must reflect real load, and a flaky candidate must not
disturb production.

Fail-open vs raise — the default policy
---------------------------------------

The layer's error policy has two pieces and is the *only* policy
the consumers of ``inference_models`` need to reason about.

* **Transport-level failures** are raised through to
  ``inference_error_handler``. Most map to a specific
  ``APIException`` HTTP status (500 / 503 / 504). Two paths fail
  open instead, gated by feature flags:

  * Timeouts (``httpx.TimeoutException``,
    ``requests.exceptions.Timeout``, Triton "Deadline Exceeded")
    fail open at ``violation_score=0.5`` when
    ``should_fail_open_on_model_timeout`` is on. Score 0.5 keeps the
    request in the "flagged-uncertain" range so downstream policy
    can still escalate.
  * Open circuit breaker fails open at ``violation_score=0.0`` when
    ``should_fail_open_if_circuit_breaker_open`` is on. Score 0.0
    treats the request as safe — a deliberately conservative
    default for the case where the model is fully unreachable.

* **Result-shape failures** (``MalformedModelOutput``) always fail
  open at ``violation_score=0.0``. Generative models occasionally
  emit unparseable text; the GPT-OSS path already retries the JSON
  parse once with quote/boolean normalization before raising.

The retry behaviour itself does **not** live in this package. AI-
Gateway HTTP retries are configured by ``app_context.custom_retry_config``
(tenacity, 2 attempts, ``wait_random_exponential(0.5–1.5s)``,
``_should_retry_custom_logic`` excluding 429s). Triton calls are
not retried; if the circuit breaker trips after 30 consecutive
failures the call falls through the breaker handler instead.

Pool-full as load shedding
--------------------------

Both the parallel V0/V1 image path and the model shadower
short-circuit when their gevent ``Pool`` is saturated:

* The image path falls back to V0-only when
  ``inference_pool.full()``, returning the safe default response if
  V0 itself fails to produce a ``ResponseAIImageResponse``.
* The shadower falls back to primary-only when its 20-greenlet
  pool is full.

This is the package's only intentional load-shedding mechanism, and
it is silent (logged at ``warning``, no metric event by default).
It is the correct shape for short bursts; sustained pool saturation
is what the circuit breaker, retries, and capacity alarms surface.

Cross-references
================

Backward
--------

* :ref:`architecture` — high-level service shape; this layer is the
  "model client" component on the diagram. The architecture page
  explains how ``app_context.get_prompt_moderation_service`` wires
  the factories in this package together at startup.
* :ref:`svc-moderation` — the orchestrator that calls into this
  layer per request, owns category policy
  (``PromptHarmCategory`` mapping), uses
  ``confidence/confidence_thresholds.py`` to gate verdicts, and
  uses ``inference_error_handler`` to translate transport failures
  into ``APIException`` / fail-open results.

Forward
-------

* :ref:`config-overview` — model-version feature flags
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
  ``is_custom_retry_config_enabled``), the dynamic-config keys
  ``responsible-ai-api-prompt-harm-thresholds`` and
  ``responsible-ai-api-prompt-thresholds-by-version``, the static
  config knobs ``image_moderation_v0_threshold``,
  ``image_moderation_v1_threshold``,
  ``inference_pool_size``, ``greenlet_join_timeout``,
  ``sm_endpoint_image_moderation``, ``sm_endpoint_image_moderation_v1``,
  ``teamserve_endpoint``, and ``teamserve_gptoss_endpoint``.

Verification anchors
====================

The following claims were verified against source. Each entry
points to the file and a representative location so a reader can
check by hand.

* ``model.py`` — ``InferenceModel.run_inference`` is the public
  surface (no ``predict`` / ``apredict`` / ``health_check``).
  ``HFPretrainedModelTokenizer`` exposes both ``…as_int_list`` and
  ``…as_numpy_ndarray``.
* ``errors.py`` — only two exception classes
  (``PromptModerationError``, ``MalformedModelOutput``).
* ``error_handling.py`` — ``inference_error_handler`` is a context
  manager, not a decorator. The ``except`` blocks at the top of the
  function enumerate the full handled set; each handler's branch
  is summarised in `error_handling.py — fail-open context manager`_.
* ``image_moderation_types.py`` — ``HUMAN_CLASS_ID = 0``,
  ``MODERATION_THRESHOLD = 0.4``; only three pydantic models.
* ``rai_llama.py`` — three variants in ``create_rai_llama_models``;
  Llama Teamserve uses model name
  ``teamserve-rai-optimized-logits`` version ``"1"`` for both
  V2_3_3 and V2_4. ``end_id=3934`` is the ``"false"`` token.
  Score derivation uses ``log_probs[5]`` (gRPC) /
  ``details.top_tokens[5]`` (AI-Gateway).
* ``rai_gpt_oss.py`` — ``send_chat_completions`` with
  ``reasoning_effort="low"``, ``temperature=0.0``,
  ``max_tokens=400``. JSON parse extracts the *last* ``{...}``
  block; first failure triggers quote/boolean normalization and a
  second attempt; second failure raises
  ``MalformedModelOutput``. ``violation_score`` is binary
  (``1.0`` or ``0.0``).
* ``image_moderation_sagemaker.py`` — V0 score is
  ``max`` over scores whose label equals ``HUMAN_CLASS_ID``; V1
  score is ``prediction["Unsafe"]``. Parallel path uses
  ``gevent.pool.Pool`` and ``joinall(timeout=config.greenlet_join_timeout)``.
* ``sagemaker_base.py`` — assume-role fallback to
  ``arn:aws:iam::540824312222:role/SageMakerExecutionRole``;
  ``ContentType="application/json"``.
* ``triton_grpc_client.py`` — ``CircuitBreaker(name="triton_circuit_breaker", fail_max=30)``;
  ``timeout=5*1000*1000``, ``client_timeout=6``;
  inputs always include the two boolean ``return_*`` flags.
* ``triton_openai_api_client.py`` — ``timeout=6``;
  ``Content-Type: application/json``; same circuit-breaker name.
* ``confidence/confidence_thresholds.py`` —
  ``DEFAULT_CONFIDENCE_THRESHOLD = 0.5``; ``time_cache(max_age=60)``;
  per-tenant via ``Identifiers(tenantId=…)``; per-version with
  ``"other"`` fallback. Threshold comparison is ``score >= threshold``.
* ``model_shadowing/shadower.py`` — pool size
  ``DEFAULT_MAX_POOL_SIZE = 20``; 5-second timeout on
  ``greenlet_a`` join inside ``wait_for_b``; failures swallowed
  (``logging.error("Model B failed. Skipping evaluation.")``);
  ``ShadowShim`` is the public ``InferenceModel`` wrapper.
* Tokenizers — pulled from project-root ``tokenizers/`` directory;
  ``rai_ft_v2_2`` shared by ``V2_3_3_*`` and ``V2_4_teamserve``;
  ``gpt_oss_safeguard_20b`` includes ``chat_template.jinja``
  (applied server-side, not locally on the production path);
  ``rai_ft_v2_1`` is present on disk but no factory loads it.
