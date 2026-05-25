# pyre-strict
"""
Metamate Adapters for RankEvolve.

This module provides high-level adapters for:
- DeepResearchAdapter: Execute deep research with streaming
- KnowledgeDiscoveryAdapter: Parallel search across knowledge sources
- PlatformQAAdapter: Q&A with Metamate Assistant
- DebugAssistantAdapter: Debug assistance for failure investigation

IMPORTANT: Tool names are canonical from MetamateAgentEngineTypes.php
Verify at https://www.internalfb.com/metamate/agent/tools before implementation.
"""

from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate.adapters.debug_assistant_adapter import (
    DebugAssistantAdapter,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate.adapters.deep_research_adapter import (
    DeepResearchAdapter,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate.adapters.knowledge_discovery_adapter import (
    KnowledgeDiscoveryAdapter,
)
from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate.adapters.platform_qa_adapter import (
    PlatformQAAdapter,
)

__all__ = [
    "DeepResearchAdapter",
    "KnowledgeDiscoveryAdapter",
    "PlatformQAAdapter",
    "DebugAssistantAdapter",
]
