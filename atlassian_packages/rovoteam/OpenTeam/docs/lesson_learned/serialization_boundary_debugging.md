# Lesson Learned: Verify Serialization Boundaries First

**Date:** 2026-04-18  
**Origin:** `inputmodeconfig_metadata_serialization` issue  

---

## The Pattern

When data is correct on the producer side and the consumer logic is correct, but
the consumer receives wrong/missing data — the bug is almost always at the
**serialization boundary** between them.

Serialization boundaries include:
- `to_dict()` / `from_dict()` on dataclasses
- JSON serialization for WebSocket or REST transport
- Protocol buffer / msgpack encoding
- Database ORM `to_row()` / `from_row()` methods
- Any manual mapping between internal objects and wire format

---

## The Mistake

When debugging a multi-hop data pipeline (LLM -> parser -> model -> serializer ->
WebSocket -> client -> UI), the natural instinct is to verify the "interesting" layers:
the parser logic, the type matching, the UI dispatch. The serialization layer feels
obvious — "of course `to_dict()` serializes all the fields."

But serialization methods are the most common place for **silent data loss** because:

1. **They're written once and rarely re-read.** When a new field is added to a
   dataclass, the developer updates the class definition and the code that sets the
   field, but forgets to update `to_dict()` / `from_dict()`.

2. **No compiler/type-checker catches the omission.** Python's dataclass doesn't
   auto-generate serialization. Hand-written `to_dict()` has no contract enforcement
   — missing a field is a runtime silent failure, not a build error.

3. **Tests often test layers in isolation.** Unit tests verify "parser produces correct
   object" and "UI renders correct widget for this config." Neither test catches "the
   serialized dict between them drops a field."

---

## The Rule

**When debugging "correct on both sides, wrong in the middle":**

1. Identify the serialization boundary (the function that converts between internal
   representation and wire format)
2. Read that function's source code line by line
3. Verify every field on the source object appears in the serialized output
4. Check the reverse direction too (`from_dict` / deserialization)

Do this BEFORE investigating parsing logic, type matching, or UI dispatch. The
serialization boundary is the highest-probability failure point and the fastest to
verify.

---

## Prevention

For projects with hand-written serialization, consider:

- **Round-trip tests**: `assert obj == MyClass.from_dict(obj.to_dict())` for every
  dataclass that crosses a boundary. This catches missing fields immediately.

- **Automated serialization** (Pydantic, `dataclasses_json`, attrs with cattrs): these
  auto-generate `to_dict` / `from_dict` from the class definition, eliminating the
  drift problem entirely.

- **Code review checklist**: when adding a field to a dataclass, grep for `to_dict`,
  `from_dict`, `serialize`, `deserialize` in the same file. If they exist, they need
  updating.

---

## Related Anti-Pattern: Verifying Endpoints Instead of Bottlenecks

More broadly, when debugging a data pipeline, don't just verify the first and last
hops. Identify the **narrowest point** where all data must flow through — the
bottleneck — and verify that first. In this case, every widget type's metadata flows
through a single `to_dict()` call. Verifying that one function would have found the
bug in minutes instead of hours.
