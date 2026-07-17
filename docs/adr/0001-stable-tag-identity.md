# ADR-0001: Stable tag identity foundation

- **Status:** Accepted
- **Date:** 2026-07-17
- **Decision owners:** PLC Universal Simulator maintainers
- **Related ADRs:** None
- **Related issues/documents:** `core/tag_model.py`, Phase 2A.1

## Context

Tags are currently referenced by editable engineering metadata, principally the
tag name. Future runtime and feature migrations need an identity that remains
stable when a user renames a tag or changes its address, type, direction or
feature flags.

Phase 2A.1 established in-memory identity and Phase 2A.2 persisted it in
`.simproject` files. Phase 2A.3 adopted it as the runtime-cache key. Phase 2A.4
migrates feature references without changing CSV formats or exposing IDs in the UI. Existing
callers use positional `TagDefinition` constructors with up to all nine existing
fields. Project serialization uses `TagDefinition.to_dict()`.

## Decision drivers

- Stable identity must not depend on editable PLC or display metadata.
- New identities must be generated without a central database.
- Text representation must be portable and unambiguous.
- Existing constructors, equality assumptions and serialized formats must remain
  compatible throughout the staged migration.

## Options considered

### Name or address as identity

Rejected because both values are editable, and addresses can change during PLC
engineering or vendor migration.

### Sequential integer

Rejected because it requires allocation/coordination and creates collision risk
when projects or imported data are combined.

### UUID v4

Selected because it is standard-library based, decentralized, broadly
interoperable and has negligible collision probability for this application.

## Decision

`TagDefinition` receives a final field named `tag_id`. New tags obtain an RFC
4122 UUID v4 through a default factory. The canonical representation is a
lowercase, hyphenated string such as:

```text
3f9f8f26-97a1-4ecb-8b42-05e27db21a25
```

Explicit UUID v4 values are normalized. `None`, empty values, malformed UUIDs
and UUIDs of another version are rejected. Utilities live in
`core/tag_identity.py` and have no UI/runtime dependencies.

`tag_id` is last in the dataclass to preserve every existing positional
argument. It uses `compare=False` so dataclass structural equality retains its
pre-Phase-2A.1 meaning; consumers that need stable identity compare `tag_id`
explicitly.

Name, address, data type, direction, flags and comment remain mutable metadata.
Changing them does not change `tag_id`.

## Compatibility and migration

`TagDefinition.to_dict()` emits `tag_id` as part of the complete persistable tag
definition. `from_dict()` preserves and validates an explicit identity, while a
legacy dictionary with no `tag_id` receives a new UUID.

Project schema 3 stores `tag_id` for every tag. Schema 1 and 2 projects are
migrated during staging: missing IDs are generated in the staged in-memory
representation, explicit IDs are normalized and validated, and duplicates are
rejected. Opening a legacy project never rewrites its file. The generated IDs
become persistent only after an explicit Save or Save As; reopening that saved
project preserves them.

Project schema 4 stores Dashboard and Trend membership as `*_tag_ids` lists;
Alarm, PID, digital-input and analog-profile references use explicit `tag_id`
fields with optional current `tag_name` descriptions. Digital and analog row
selections persist as `selected_tag_id`. Feedbacks have no separate relationship
schema in the current application: they are derived from tags whose direction
is `Feedback`.

Legacy names are resolved only during staging and only when unique. Required
Alarm and non-empty PID references reject loading when invalid, missing or
ambiguous. Stale optional membership, profile and row-selection references are
cleared with migration diagnostics. Opening still never rewrites the source;
Save or Save As persists schema 4 references.

`RuntimeTagCache` stores synchronized volatile state by canonical `tag_id`.
Names remain display metadata and a transitional compatibility lookup. A rename
therefore preserves value, validity, timestamp and source when the tag's
runtime-relevant signature is unchanged. Replacing a tag with another identity,
even with the same name or address, does not transfer runtime state.

Explicit ID-based operations are the unambiguous runtime API. Name lookup is
accepted only when it resolves to zero or one synchronized identity; multiple
matches raise `AmbiguousTagNameError`. A synchronized population containing a
duplicate ID is rejected before cache mutation. Legacy name-keyed, in-memory
snapshots can be restored only through a unique current name mapping.

The alias `Tag = TagDefinition` and all existing constructors remain supported.
No ID is displayed in the UI.

## Consequences

### Positive

- Newly created tags have an explicit identity independent of mutable metadata.
- Ordinary `copy.copy`/`copy.deepcopy` preserve the string ID, supporting
  snapshots and rollback.
- Invalid explicit identities fail immediately and consistently.
- Legacy project migration remains transactional and occurs before application
  state is mutated.

### Negative

- Two independent opens of an unsaved legacy project generate different IDs;
  the identity becomes stable across opens after the project is saved.
- Dataclass equality remains structural and is not an identity comparison.
- Code must compare `tag_id` explicitly when identity semantics are required.

### Neutral or operational

No distinct user-facing “Duplicate tag” operation exists in the reviewed code.
When one is introduced, it must create a new UUID rather than copying the source
ID. This behavior is deferred rather than inferred from rollback copying.

## Deferred work

- generic, TIA and Schneider CSV decisions;
- user-facing duplication semantics and UI exposure, if ever required.

## Verification

- UUID generation, uniqueness, normalization and validation tests;
- positional and keyword constructor regression tests;
- mutation and `deepcopy` identity-preservation tests;
- explicit structural-equality test;
- project save/reopen tests proving IDs are persisted and preserved;
- invalid and duplicate project identity rejection and rollback tests;
- runtime rename, replacement, ambiguity, reconciliation and snapshot tests;
- feature resolver, legacy migration, rename and replacement tests;
- complete project, CSV and runtime regression suites.

## Follow-up actions

- [x] Persist stable IDs with backward-compatible staged project migration.
- [x] Adopt stable IDs as the primary runtime-cache key.
- [x] Persist feature references by stable ID with staged legacy migration.
