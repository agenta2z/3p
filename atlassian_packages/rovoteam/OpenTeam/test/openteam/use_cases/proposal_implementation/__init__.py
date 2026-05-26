"""Jira-board-and-PR-monitor prototype.

Hackily monitors a Jira Epic; auto-executes child issues assigned to the user
by invoking RovoDevCliInferencer to create PRs; then monitors those PRs and
auto-replies to comments / CI failures until merged.

This is a PROOF-OF-CONCEPT, not production code. See README.md.
"""
