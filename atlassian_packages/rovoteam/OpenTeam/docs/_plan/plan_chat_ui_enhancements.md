# Chat UI Enhancements — Markdown Fix & View Full Response Tabs

## What Was Already Built (No Action Needed)

After reading every relevant file in full:

| Feature | Status |
|---|---|
| "Full Response" button in `AgentMessageBubble` (overflow detection) | ✅ Already implemented |
| `usePromptViewer.openFullResponse(content)` | ✅ Already implemented |
| `PromptViewerDrawer` full-response mode (single `MarkdownRenderer` view) | ✅ Already implemented |
| `ManagerChatView` wires `onViewFullResponse={promptViewer.openFullResponse}` | ✅ Already implemented |

What remains: (1) fix markdown rendering, (2) upgrade Full Response mode to two tabs.

---

## Root Cause Analysis: Why Bullets Look "Connected"

There are **two distinct problems** that compound each other:

### Problem A — Unicode bullet characters (• U+2022) not recognized as list markers

The LLM often outputs:
```
• AI Customer Support Agent — handles tickets
• AI Project Manager — tracks tasks
```

`react-markdown` only recognizes `-`, `*`, `+` as Markdown list markers. Unicode `•` is treated as plain text, so each `•` line renders as a paragraph — not a `<ul><li>` list.

**Fix:** Preprocess content before passing to ReactMarkdown, converting `•` lines to `- ` markers.

### Problem B — `'& p': { m: 0 }` collapses ALL paragraph spacing

Both `AgentMessageBubble.js` (line 157) and `StreamingMessage.js` (line 100) have:
```jsx
'& p': { m: 0 },
```

When react-markdown renders proper markdown lists (`- item`), each `<li>` wraps its text in `<p>`. With `m: 0`, those `<p>` tags have no margin → list items appear squashed together.

Also affects multi-paragraph responses: each `<p>` is margin-less → paragraphs run together.

**Fix:** More targeted CSS that zeroes paragraph margins only at the top level, and adds spacing at the `li` level.

**Note:** For inline `•` bullets on a single line (e.g., `🏗️ Section • item1 • item2` all on one line), neither fix helps — that's a prompt/LLM output format issue, not a rendering issue.

---

## Implementation Plan

### Step 1 — `preprocessContent()` in `MarkdownRenderer.js`

**File:** `ui/src/components/chat/MarkdownRenderer.js`

Add before the `MarkdownRenderer` export:

```javascript
/**
 * Normalize LLM output before markdown parsing.
 * - Converts Unicode bullet characters (•·‣⁃) at line start to markdown list markers (-)
 * - Inserts required blank line before list blocks that follow a paragraph
 *   (markdown spec requires blank line before a list to be parsed as a list)
 */
function preprocessContent(content) {
  if (!content) return content;
  let text = content;

  // Convert line-start Unicode bullets to markdown list markers
  // Matches: optional leading whitespace + bullet char + whitespace + rest
  text = text.replace(/^[ \t]*[•·‣⁃]\s+/gm, '- ');

  // Ensure blank line before list blocks so markdown parser treats them as lists
  // (without this, a list immediately following a paragraph is not parsed as a list)
  text = text.replace(/([^\n])\n(- )/g, '$1\n\n$2');

  return text;
}
```

Apply it in `MarkdownRenderer`:
```jsx
export function MarkdownRenderer({ content, components = {} }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ code: CodeComponent, ...TableComponents, ...components }}>
      {preprocessContent(content)}
    </ReactMarkdown>
  );
}
```

**Why this is safe:** Pure string transformation before rendering. No React state, no side effects. The blank-line insertion regex only fires between a non-newline character and a `- ` line, which is exactly the "paragraph immediately followed by list" pattern that markdown requires a blank line for.

---

### Step 2 — CSS fix in `AgentMessageBubble.js`

**File:** `ui/src/components/chat/AgentMessageBubble.js`

**Location:** The content `Box` sx at line ~155 (inside `<Collapse>`):

```jsx
// BEFORE:
sx={{
  ...
  maxHeight: MAX_BODY_HEIGHT,
  overflow: 'auto',
  '& p': { m: 0 },
  '& pre': { overflow: 'auto' },
}}

// AFTER:
sx={{
  ...
  maxHeight: MAX_BODY_HEIGHT,
  overflow: 'auto',
  '& p': { m: 0 },              // top-level paragraphs: no margin (keeps single-line replies tight)
  '& p:last-child': { mb: 0 },  // last paragraph: no trailing gap
  '& li p': { m: 0 },           // p inside li: keep tight (li provides its own spacing)
  '& li': { mb: 0.25 },         // gentle gap between list items (~2px)
  '& ul, & ol': { pl: 2.5, mt: 0.5, mb: 0.5 },  // indent lists + breathing room
  '& pre': { overflow: 'auto' },
}}
```

**Why this CSS approach (vs. other option):**
- Keeps `'& p': { m: 0 }` for top-level paragraphs — avoids padding above/below simple short replies
- `p:last-child { mb: 0 }` prevents trailing gap at bottom of bubble
- Adds spacing at `li` level (not `p` level) — correct place for list item separation
- `ul/ol` gets indent (`pl: 2.5`) and top/bottom breathing room

---

### Step 3 — CSS fix in `StreamingMessage.js`

**File:** `ui/src/components/chat/StreamingMessage.js`

**Location:** Line ~100 content Box:

```jsx
// BEFORE:
<Box sx={{ p: 2, '& p': { m: 0 }, '& pre': { overflow: 'auto' } }}>

// AFTER:
<Box sx={{
  p: 2,
  '& p': { m: 0 },
  '& p:last-child': { mb: 0 },
  '& li p': { m: 0 },
  '& li': { mb: 0.25 },
  '& ul, & ol': { pl: 2.5, mt: 0.5, mb: 0.5 },
  '& pre': { overflow: 'auto' },
}}>
```

Same rules as AgentMessageBubble for visual consistency between streaming and settled messages.

---

### Step 4 — Two-tab Full Response mode in `PromptViewerDrawer.js`

**File:** `ui/src/components/chat/PromptViewerDrawer.js`

**Current state:** Full Response mode has a single `<MarkdownRenderer>` view — no tabs.

**Change:** Add "Rendered" and "Raw" tabs in Full Response mode.

```jsx
// Add at top of file alongside PROMPT_TABS:
const RESPONSE_TABS = ['Rendered', 'Raw'];

// Inside PromptViewerDrawer component, add new state:
const [responseTab, setResponseTab] = useState(0);

// Reset responseTab to 0 when switching between modes:
useEffect(() => { setResponseTab(0); }, [isFullResponse]);

// Replace the current isFullResponse block:
{isFullResponse && (
  <>
    <Tabs
      value={responseTab}
      onChange={(_, v) => setResponseTab(v)}
      sx={{
        borderBottom: '1px solid rgba(255,255,255,0.08)',
        px: 2,
        flexShrink: 0,
        minHeight: 40,
        '& .MuiTab-root': { minHeight: 40, fontSize: '0.8rem', py: 0 },
      }}
    >
      {RESPONSE_TABS.map((label, i) => (
        <Tab key={label} label={label} value={i} />
      ))}
    </Tabs>
    <Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>
      {responseTab === 0 && <MarkdownRenderer content={fullResponseContent} />}
      {responseTab === 1 && <CodeBlock content={fullResponseContent} />}
    </Box>
  </>
)}
```

**Also remove** the old single-content block from the `<Box sx={{ flex: 1, overflow: 'auto', p: 2 }}>` wrapper since tabs now manage their own content area.

**Imports needed:** Add `useEffect` to the existing React import.

**Why two tabs are valuable:**
- "Rendered" — shows markdown with proper formatting (same as bubble but uncapped height)
- "Raw" — shows plain text in monospace `pre` block, useful for copy-pasting the full response or debugging LLM output format

**Tab state reset:** The `useEffect` resetting `responseTab` to 0 when `isFullResponse` changes is **critical** — without it, if the user was on "Raw" tab and then opens a Prompt view (switching to prompt mode) and then comes back to Full Response, they'd land on "Raw" again unexpectedly. This was missing from the other plan.

---

### Step 5 — Verify `message.content` cleanliness for drawer (check `useManagerChat`)

**File:** `ui/src/hooks/useManagerChat.js`

Before implementing, verify: does `message.content` stored in the messages array already have tool-call XML stripped? 

- If yes: `onViewFullResponse(message.content)` in `AgentMessageBubble.js` line ~111 is already correct. ✅
- If no: wrap with `stripToolsToInvoke`: 
  ```jsx
  onViewFullResponse && onViewFullResponse(stripToolsToInvoke(message.content || ''))
  ```
  (`stripToolsToInvoke` is already imported from `ThinkingFold` at the top of `AgentMessageBubble.js`)

**The other agent's plan assumed this is already clean without verifying. My plan flags it as a verification step.**

---

## Files to Modify

| File | Change | Complexity |
|---|---|---|
| `components/chat/MarkdownRenderer.js` | Add `preprocessContent()` function, apply to render | Trivial |
| `components/chat/AgentMessageBubble.js` | Replace CSS rules in content Box + verify `stripToolsToInvoke` | Trivial |
| `components/chat/StreamingMessage.js` | Replace CSS rules in content Box | Trivial |
| `components/chat/PromptViewerDrawer.js` | Add two-tab Full Response mode + `useEffect` reset | Small |

**Files NOT to modify:**
- `usePromptViewer.js` — already correct
- `ManagerChatView.js` — already wired correctly

---

## Verification Checklist

1. **Unicode bullets:** Send a message that gets a `•`-bulleted response. Verify bullets render as proper `<ul><li>` items with indent and spacing.
2. **Markdown list syntax:** Send a message that gets a `- ` or `* ` bulleted response. Verify proper rendering with item spacing.
3. **Multi-paragraph response:** Verify multiple paragraphs have visible separation (not collapsed into a wall).
4. **Short single-line reply:** Verify simple short replies don't have extra padding top/bottom (paragraph margin stays 0).
5. **"Full Response" button:** Only appears when content exceeds 320px. Click it → drawer opens.
6. **"Rendered" tab:** Full markdown-rendered response, no height cap.
7. **"Raw" tab:** Same content in monospace `CodeBlock`, scrollable.
8. **Tab reset:** Switch from Full Response → close → View Prompt → close → Full Response again → lands on "Rendered" tab (not "Raw").
9. **Prompt Inspector unaffected:** View Prompt still shows Template / Variables / Rendered Prompt tabs.
10. **Streaming messages:** Bullet points render correctly in `StreamingMessage` during active streaming.

---

## Estimated Effort

| Step | Time |
|---|---|
| `MarkdownRenderer.js` — preprocessContent | 5 min |
| `AgentMessageBubble.js` — CSS fix + verify strip | 5 min |
| `StreamingMessage.js` — CSS fix | 2 min |
| `PromptViewerDrawer.js` — two-tab Full Response | 10 min |
| Testing | 10 min |
| **Total** | **~30 min** |
