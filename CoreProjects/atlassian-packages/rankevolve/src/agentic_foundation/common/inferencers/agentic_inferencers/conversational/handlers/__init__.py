# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.
# pyre-strict
"""Built-in conversation tool handlers + default registry factory.

Diff 1b lands an empty `default_registry()` so the inferencer wiring (Diff 1c)
can fall back to legacy if/elif branches for every tool type. Subsequent diffs
register concrete handlers one by one. Diff 5b validates that every
`ConversationToolType` value has a registered handler.
"""

from __future__ import annotations

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handler_registry import (
    ConversationToolHandlerRegistry,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.clarification import (
    ClarificationHandler,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.confirmation import (
    ConfirmationHandler,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.multiple_choice import (
    MultipleChoiceHandler,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.proposal_selection import (
    ProposalSelectionHandler,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.single_choice import (
    SingleChoiceHandler,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.conversational.handlers.tool_argument_form import (
    ToolArgumentFormHandler,
)


def default_registry() -> ConversationToolHandlerRegistry:
    """Build the framework-default registry of all 6 built-in handlers.

    Diff 5a complete: every declared `ConversationToolType` value has a handler.
    Diff 5b will add `__attrs_post_init__` validation to enforce this on every
    `ConversationalInferencer` construction.
    """
    reg = ConversationToolHandlerRegistry()
    reg.register(ClarificationHandler())
    reg.register(SingleChoiceHandler())
    reg.register(MultipleChoiceHandler())
    reg.register(ConfirmationHandler())
    reg.register(ProposalSelectionHandler())
    reg.register(ToolArgumentFormHandler())
    return reg
