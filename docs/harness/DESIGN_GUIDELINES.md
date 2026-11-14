# Design Guidelines

> Owners: design standards `ux-designer` · implementation sync (actual tokens, component list) `frontend-developer`
> **The canonical design rules are [`/.claude/.rules/design.md`](../../.claude/.rules/design.md)** (principles, color, layout, cards, buttons, forms, typography). Don't copy rules here. This doc holds the actual tokens, the component list, and per-screen UX standards.

## Design tokens (actual values, `frontend/src/index.css`)

| Token | Value | Use |
|---|---|---|
| `brand-50` / `100` / `200` | `#faf5ff` / `#f3e8ff` / `#e9d5ff` | Background emphasis, selected state |
| `brand-300` / `400` | `#d8b4fe` / `#c084fc` | Secondary emphasis, borders |
| `brand-500` | `#aa3bff` | Primary brand color |
| `brand-600` / `700` | `#9333ea` / `#7e22ce` | Primary button hover/active, links |
| Neutral | Tailwind default gray scale | Text and backgrounds (avoid pure black) |

Add new tokens only in `@theme` in `index.css`, and update this table with them. No hardcoded hex or arbitrary values (`[#...]`).

## Patterns in use (from the code, 2026-11-14)

- Corners: `rounded-lg` by default; cards/bubbles `rounded-2xl`; badges and avatars `rounded-full`.
- Shadows: almost unused (`shadow-sm` in one place) — consistent with the rule "no heavy shadows".
- Max content width: mostly `max-w-3xl` (chat, forms); wide screens `max-w-4xl`.

## Component list (reuse first)

| Area | Components | Path |
|---|---|---|
| Common | `Layout`, `ProtectedRoute` | `src/components/` |
| Chat | `ChatInput`, `MessageBubble` | `src/components/chat/` |
| Collections | `CollectionListItem`, `CreateCollectionForm`, `EditCollectionForm` | `src/components/collections/` |
| Documents | `CollectionInfoPanel`, `DocumentRow`, `DocumentUpload`, `IngestProgress`, `StatusBadge`, `UploadZone` | `src/components/documents/` |

There are no shared Button / Card / Input components yet. When the same style repeats in 2+ places, extract a shared component (`frontend-developer`, design check by `ux-designer`).

## UX standards (every screen)

- Every async action has loading / empty / error / success states. Error messages say what happened and what to do. Keep user input on error.
- Agent answers can take several seconds: show progress, keep the input usable, allow retry.
- Citations show their source (document/collection or web URL) distinctly and are checkable.
- Show document ingest status (`UPLOADED → PARSING → EMBEDDING → INDEXED / FAILED`) readably, with the next step on failure.
- Destructive actions such as delete state the result and ask for confirmation. Prevent duplicate runs (double click).

## Responsive and accessibility standards

- Works from mobile (390px) to desktop with no horizontal scroll. Touch targets ≥ 44px.
- WCAG 2.2 AA: contrast, visible focus, fully keyboard-operable, a label for every input, never convey state by color alone.
- Announce new chat messages and ingest status changes with `aria-live`.

## Per-screen design specs

When `ux-designer` writes a screen spec, add a link below.

| Screen | Spec | Date |
|---|---|---|
| — | (none) | |
