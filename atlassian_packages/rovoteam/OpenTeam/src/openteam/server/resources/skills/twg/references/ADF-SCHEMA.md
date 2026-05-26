# ADF Quick Reference

Derived from `@atlaskit/adf-schema@52.2.2`. For details on any node or mark, use the URL patterns below.

## Deep reference URLs

- Per-node docs: `https://developer.atlassian.com/platform/atlassian-document-format/concepts/document-structure/nodes/{node_name}/`
- Per-mark docs: `https://developer.atlassian.com/platform/atlassian-document-format/concepts/document-structure/marks/{mark_name}/`
- Visual examples: `https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/`
- Full JSON schema: `https://unpkg.com/@atlaskit/adf-schema@52.2.2/dist/json-schema/v1/full.json`

## Document envelope

```json
{"version":1,"type":"doc","content":[...block nodes...]}
```

Omit `localId` in all nodes when creating or updating pages.

## Block nodes

| Node | Required attrs | Children |
|---|---|---|
| `paragraph` | — | inline nodes |
| `heading` | `level` (1–6) | inline nodes |
| `bulletList` | — | `listItem` |
| `orderedList` | `order` (number, optional) | `listItem` |
| `listItem` | — | `paragraph`, `bulletList`, `orderedList`, `mediaSingle`, `codeBlock` |
| `codeBlock` | `language` (string, optional) | single `text` node, no marks |
| `blockquote` | — | `paragraph`, `bulletList`, `orderedList`, `codeBlock` |
| `table` | `layout` (optional) | `tableRow` |
| `tableRow` | — | `tableCell`, `tableHeader` |
| `tableCell` | — | block nodes |
| `tableHeader` | — | block nodes |
| `panel` | `panelType`: `info`/`note`/`tip`/`warning`/`error` | `paragraph`, `heading`, `bulletList`, `orderedList`, `codeBlock`, `rule` |
| `expand` | `title` (string) | non-nestable block nodes, `nestedExpand` |
| `nestedExpand` | `title` (string) | non-nestable block nodes |
| `rule` | — | — (no children) |
| `mediaSingle` | — | `media` |
| `mediaGroup` | — | `media` |
| `extension` | `extensionKey`, `extensionType` (both required) | — |
| `bodiedExtension` | `extensionKey`, `extensionType` (both required) | block nodes |
| `taskList` | — | `taskItem` |
| `taskItem` | `state`: `TODO`/`DONE` | inline nodes |

## Inline nodes

| Node | Required attrs |
|---|---|
| `text` | `text` (non-empty string) |
| `mention` | `id` (string) |
| `emoji` | `shortName` (string) |
| `date` | `timestamp` (string) |
| `status` | `text` (string), `color`: `neutral`/`purple`/`blue`/`red`/`yellow`/`green` |
| `hardBreak` | — |
| `inlineCard` | `url` (string) |
| `mediaInline` | `id` (string), `collection` (string) |

## Marks

Applied to `text` nodes only via a `marks` array.

| Mark | Attrs |
|---|---|
| `strong` | — |
| `em` | — |
| `code` | — |
| `strike` | — |
| `underline` | — |
| `link` | `href` (required) |
| `textColor` | `color` (required, hex string) |
| `subsup` | `type`: `sub`/`sup` (required) |

## Examples

**Paragraph with bold + link:**
```json
{"type":"paragraph","content":[{"type":"text","text":"Hello "},{"type":"text","text":"world","marks":[{"type":"strong"}]},{"type":"text","text":" see "},{"type":"text","text":"docs","marks":[{"type":"link","attrs":{"href":"https://example.com"}}]}]}
```

**Heading:**
```json
{"type":"heading","attrs":{"level":2},"content":[{"type":"text","text":"Section Title"}]}
```

**Table with header row:**
```json
{"type":"table","content":[{"type":"tableRow","content":[{"type":"tableHeader","content":[{"type":"paragraph","content":[{"type":"text","text":"Name"}]}]},{"type":"tableHeader","content":[{"type":"paragraph","content":[{"type":"text","text":"Status"}]}]}]},{"type":"tableRow","content":[{"type":"tableCell","content":[{"type":"paragraph","content":[{"type":"text","text":"Alpha"}]}]},{"type":"tableCell","content":[{"type":"paragraph","content":[{"type":"status","attrs":{"text":"Done","color":"green"}}]}]}]}]}
```

**Panel:**
```json
{"type":"panel","attrs":{"panelType":"warning"},"content":[{"type":"paragraph","content":[{"type":"text","text":"Check dependencies before proceeding."}]}]}
```

**Expand:**
```json
{"type":"expand","attrs":{"title":"Details"},"content":[{"type":"paragraph","content":[{"type":"text","text":"Hidden content here."}]}]}
```

## Common pitfalls

- `text` nodes must have non-empty `text` — empty strings are invalid
- `listItem` wraps block nodes (usually `paragraph`), never raw text
- `tableRow` children must be `tableCell` or `tableHeader`, not mixed arbitrarily
- `panel` requires `panelType` attr — omitting it is invalid
- marks go on `text` nodes only, not on block or other inline nodes
- `codeBlock` content is a single `text` node with no marks
- omit `localId` in all nodes when creating or updating
