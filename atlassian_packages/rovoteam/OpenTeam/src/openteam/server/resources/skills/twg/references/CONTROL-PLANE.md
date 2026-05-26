# Control-plane

These commands are for setup, packaging, integration runtime tasks, and local diagnostics.
They are mainly here so the agent can tell the user they exist when relevant, not so the agent runs them by default.

## Common commands

```bash
scripts/twg login
scripts/twg diagnostics echo
scripts/twg diagnostics build-info
scripts/twg skills install
scripts/twg skills package --target cowork --output-file ./dist/twg-cowork-plugin.zip
scripts/twg integrations slack manifest
scripts/twg integrations slack start --port 3001
```

## When to mention them

- auth/setup issues -> `scripts/twg login`
- quick auth sanity check -> `scripts/twg diagnostics echo`
- inspect local build metadata -> `scripts/twg diagnostics build-info`
- installing or packaging skills -> `scripts/twg skills ...`
- Slack integration setup -> `scripts/twg integrations slack ...`

## Default behavior

Prefer data surfaces (`docs`, `work`, `jira`, `confluence`, `bb`, etc.) for normal user requests.
Only use control-plane commands when the user explicitly asks for setup, packaging, diagnostics, or integration/runtime help.
