---
name: slack_actions
description: >
  Control Slack interactions — react to messages, manage pins, send/edit/delete messages,
  and fetch member info. Uses bot token (SLACK_BOT_TOKEN) or falls back to user token.
labels:
  - slack
  - actions
  - communication
metadata:
  requires:
    env: [SLACK_BOT_TOKEN]
  tools:
    - slack_react
    - slack_remove_reaction
    - slack_list_reactions
    - slack_remove_own_reactions
    - slack_send_message
    - slack_edit_message
    - slack_delete_message
    - slack_read_messages
    - slack_pin_message
    - slack_unpin_message
    - slack_list_pins
    - slack_member_info
    - slack_emoji_list
---

# Slack Actions

## Overview

Use Slack action tools to react, manage pins, send/edit/delete messages, and fetch member
info. These tools use the bot token configured via `SLACK_BOT_TOKEN` environment variable.

## Prerequisites

- `SLACK_BOT_TOKEN` env var set (xoxb-* bot token with appropriate scopes)
- Falls back to user token (`SLACK_XOXC_TOKEN` / `SLACK_USER_TOKEN`) if bot token not available

## Inputs to collect

- `channel_id` and `message_id` (Slack message timestamp, e.g. `1712023032.1234`)
- For reactions, an `emoji` (Unicode or `:name:`)
- For message sends, a `to` target (`channel:C123` or `user:U123`) and `content`

## Action Groups

| Group | Tools | Notes |
|-------|-------|-------|
| Reactions | `slack_react`, `slack_remove_reaction`, `slack_list_reactions`, `slack_remove_own_reactions` | Add/remove/list emoji reactions |
| Messaging | `slack_send_message`, `slack_edit_message`, `slack_delete_message`, `slack_read_messages` | Send/edit/delete/read messages |
| Pins | `slack_pin_message`, `slack_unpin_message`, `slack_list_pins` | Pin/unpin/list pinned items |
| Info | `slack_member_info`, `slack_emoji_list` | User profiles and custom emojis |

## Examples

### React to a message
```
slack_react C123 1712023032.1234 ✅
```

### List reactions
```
slack_list_reactions C123 1712023032.1234
```

### Send a message
```
slack_send_message channel:C123 "Hello from the agent"
```

### Send a threaded reply
```
slack_send_message channel:C123 "Replying in thread" --thread_ts 1712023032.1234
```

### Send a DM
```
slack_send_message user:U456 "Direct message to user"
```

### Edit a message
```
slack_edit_message C123 1712023032.1234 "Updated text"
```

### Delete a message
```
slack_delete_message C123 1712023032.1234
```

### Read recent messages
```
slack_read_messages C123 --limit 20
```

### Read thread replies
```
slack_read_messages C123 --thread_id 1712023032.1234
```

### Pin a message
```
slack_pin_message C123 1712023032.1234
```

### Unpin a message
```
slack_unpin_message C123 1712023032.1234
```

### List pinned items
```
slack_list_pins C123
```

### Member info
```
slack_member_info U123
```

### Emoji list
```
slack_emoji_list --limit 50
```

## Ideas

- React with ✅ to mark completed tasks
- Pin key decisions or weekly status updates
- Send summary messages to team channels after completing analysis
