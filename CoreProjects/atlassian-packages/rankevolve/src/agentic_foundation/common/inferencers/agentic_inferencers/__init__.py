"""Agentic inferencers package.

This package provides inferencer implementations for agentic AI interactions,
including reflective inferencers and external SDK-based inferencers.

External SDK inferencers (ClaudeCodeInferencer, DevmateSDKInferencer) use lazy
imports to avoid requiring their SDKs at import time. This allows code that
doesn't use these inferencers to import the package without the SDK dependencies.
"""

# Lazy imports for external SDK inferencers
# These are not imported at module level to avoid requiring the SDKs


def __getattr__(name):
    """Lazy import external SDK inferencers."""
    if name == "ClaudeCodeInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.claude_code import (
            ClaudeCodeInferencer,
        )

        return ClaudeCodeInferencer
    elif name == "DevmateSDKInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.devmate import (
            DevmateSDKInferencer,
        )

        return DevmateSDKInferencer
    elif name == "SDKInferencerResponse":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external import (
            SDKInferencerResponse,
        )

        return SDKInferencerResponse
    elif name == "DualInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.dual_inferencer import (
            DualInferencer,
        )

        return DualInferencer
    elif name == "ReflectiveInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.reflective_inferencer import (
            ReflectiveInferencer,
        )

        return ReflectiveInferencer
    elif name == "MetamateSDKInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate import (
            MetamateSDKInferencer,
        )

        return MetamateSDKInferencer
    elif name == "MetamateCliInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.external.metamate import (
            MetamateCliInferencer,
        )

        return MetamateCliInferencer
    elif name == "LinearWorkflowInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.linear_workflow_inferencer import (
            LinearWorkflowInferencer,
        )

        return LinearWorkflowInferencer
    elif name == "WorkflowStepConfig":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.linear_workflow_inferencer import (
            WorkflowStepConfig,
        )

        return WorkflowStepConfig
    elif name == "PlanThenImplementInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.plan_then_implement_inferencer import (
            PlanThenImplementInferencer,
        )

        return PlanThenImplementInferencer
    elif name == "BreakdownThenAggregateInferencer":
        from rankevolve.src.agentic_foundation.common.inferencers.agentic_inferencers.flow_inferencers.breakdown_then_aggregate_inferencer import (
            BreakdownThenAggregateInferencer,
        )

        return BreakdownThenAggregateInferencer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BreakdownThenAggregateInferencer",
    "ClaudeCodeInferencer",
    "DevmateSDKInferencer",
    "DualInferencer",
    "LinearWorkflowInferencer",
    "MetamateCliInferencer",
    "MetamateSDKInferencer",
    "PlanThenImplementInferencer",
    "ReflectiveInferencer",
    "SDKInferencerResponse",
    "WorkflowStepConfig",
]
