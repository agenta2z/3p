---
name: slack_search
description: >
  Search and retrieve Slack data — messages, files, channels, threads, and DMs.
  Provides enterprise-wide search using user token authentication with automatic
  token refresh via the proximity server.
labels:
  - slack
  - search
  - communication
metadata:
  requires:
    env: [SLACK_USER_TOKEN]
    env_optional: [SLACK_XOXC_TOKEN, SLACK_XOXD_TOKEN_ENCODED, PROXIMITY_URL]
  tools:
    - slack_search_messages
    - slack_search_files
    - slack_get_thread
    - slack_list_channels
    - slack_find_channel
    - slack_find_dm_channel
    - slack_get_channel_history
    - slack_get_dm_messages
---

# Slack Search

## Overview

Search and retrieve Slack data using 8 specialized tools. Each tool maps to a Slack Web API
endpoint with automatic authentication and token refresh.

## Available Tools

| Tool | Purpose |
|------|---------|
| `slack_search_messages` | Search messages across all channels |
| `slack_search_files` | Search files shared in Slack |
| `slack_get_thread` | Get all replies in a thread |
| `slack_list_channels` | List accessible channels (paginated) |
| `slack_find_channel` | Resolve a channel name to its ID |
| `slack_find_dm_channel` | Find the DM channel with a specific user |
| `slack_get_channel_history` | Get recent messages from a channel or DM |
| `slack_get_dm_messages` | Get DM messages with a user, with optional sender filter |

## Common Patterns

```
# Search for messages
slack_search_messages "deployment issues" --count 10

# Find a channel and read its history
slack_find_channel --channel_name team-ai-lab
slack_get_channel_history C1234567890 --limit 20

# Read a thread
slack_get_thread C1234567890 1234567890.123456

# Get DMs with someone
slack_get_dm_messages U1234567890 --limit 10
```

## Authentication

Token priority (checked in order):
1. `SLACK_XOXC_TOKEN` + `SLACK_XOXD_TOKEN_ENCODED` (session tokens)
2. Proximity server at `PROXIMITY_URL` (auto-refresh from Slack desktop)
3. `SLACK_USER_TOKEN` (user OAuth token, fallback)

On auth failure, automatically retries with fresh tokens from the proximity server.

## Notes

- `slack_get_channel_history` has a dual-API fallback: tries `conversations.history` first,
  falls back to `search.messages` if the bot/user isn't in the channel.
- `slack_get_dm_messages` is also available as `slack_get_messages_with_user` (alias).
- Channel listing paginates by default — large workspaces may take several API calls.
