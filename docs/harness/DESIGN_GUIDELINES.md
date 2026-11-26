# Design Guidelines

> Owners: design standards `ux-designer` · implementation sync (actual tokens, component list) `frontend-developer`
> **The canonical design rules are [`/.claude/.rules/design.md`](../../.claude/.rules/design.md)** (principles, color, layout, cards, buttons, forms, typography). Don't copy rules here. This doc holds the actual tokens, the component list, and per-screen UX standards.

## Design tokens (actual values, `frontend/src/index.css`)

Visual system: `.claude/design/DESIGN-spotify.md` (D-015). `color-scheme: dark` on `html`.

| Token (Tailwind name) | Value | Use |
|---|---|---|
| `canvas` | `#121212` | Page background, header/divider lines on cards |
| `surface` / `surface-2` | `#181818` / `#1f1f1f` | Sidebar, cards / inputs, stat tiles, row hover |
| `surface-3` / `surface-4` | `#252525` / `#272727` | Active nav, user bubble, hover / chips, progress track |
| `fg` | `#ffffff` | Primary text, focus outline/ring |
| `muted` / `soft` | `#b3b3b3` / `#cbcbcb` | Secondary text, inactive nav / slightly brighter secondary |
| `primary` / `primary-strong` | `#1ed760` / `#1db954` | Primary CTA, active/status, checkbox accent / CTA hover. Never decorative |
| `negative` / `warning` / `info` | `#f3727f` / `#ffa42b` / `#539df5` | Error / warning / info states |
| `line` / `line-strong` | `#4d4d4d` / `#7c7c7c` | Dashed drop zone / outlined pill border, inset input border |
| `shadow-medium` / `shadow-heavy` | `0 8px 8px rgb(0 0 0/.3)` / `0 8px 24px rgb(0 0 0/.5)` | Elevated cards / dialogs, menus, login card |
| `shadow-inset-border` | `0 1px 0 #121212, inset 0 0 0 1px #7c7c7c` | Inputs |
| `text-2xs` | `0.6875rem` | Badges, chunk labels |
| `tracking-button` | `1.4px` | Primary button label |
| `font-sans` | Helvetica Neue, Helvetica, Arial, Pretendard, Apple SD Gothic Neo, Malgun Gothic, Noto Sans KR, sans-serif | Only font stack |

Add new tokens only in `@theme` in `index.css`, and update this table with them. No hardcoded hex or arbitrary values (`[#...]`).

## Patterns in use (from the code, 2026-11-26)

- Shared control utilities (`@utility` in `index.css`): `btn-primary` (green pill, black uppercase label), `btn-secondary` (outlined pill), `btn-ghost` (text pill), `btn-danger` (negative outlined pill), `field` (dark pill input/select; textareas get `rounded-lg`). Use these instead of re-typing classes.
- Cards: `rounded-lg bg-surface`, no borders; list rows `hover:bg-surface-2`; inner dividers `border-canvas` / `divide-canvas`.
- Errors: `rounded-lg bg-negative/10 text-negative`. Status: `bg-primary/10 text-primary`.
- Nav: active `bg-surface-3 font-bold text-fg`, inactive `text-muted`.
- Page titles `text-2xl font-bold`; section titles `text-base font-bold`.
- Max content width: mostly `max-w-3xl` (chat, forms); wide screens `max-w-4xl`.

## Component list (reuse first)

| Area | Components | Path |
|---|---|---|
| Common | `Layout`, `ProtectedRoute` | `src/components/` |
| Chat | `ChatInput`, `MessageBubble` | `src/components/chat/` |
| Collections | `CollectionListItem`, `CreateCollectionForm`, `EditCollectionForm` | `src/components/collections/` |
| Documents | `CollectionInfoPanel`, `DocumentRow`, `DocumentUpload`, `IngestProgress`, `StatusBadge`, `UploadZone` | `src/components/documents/` |

Buttons and inputs share the CSS utilities above (no React wrapper yet). When a style repeats in 2+ places, extract a utility or shared component (`frontend-developer`, design check by `ux-designer`).

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
