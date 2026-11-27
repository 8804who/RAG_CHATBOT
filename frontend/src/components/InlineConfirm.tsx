interface InlineConfirmProps {
  prompt: string
  pending: boolean
  onConfirm: () => void
  onCancel: () => void
}

/**
 * Inline "Delete? Confirm / Cancel" step for destructive row actions. Focus
 * moves to Confirm when it opens; callers return focus to their trigger on
 * cancel (the trigger is unmounted while this is shown).
 */
export function InlineConfirm({
  prompt,
  pending,
  onConfirm,
  onCancel,
}: InlineConfirmProps): React.JSX.Element {
  return (
    <span className="flex items-center gap-2 text-sm">
      <span className="text-muted">{prompt}</span>
      <button
        type="button"
        onClick={onConfirm}
        disabled={pending}
        autoFocus
        className="inline-flex min-h-11 items-center rounded-full bg-negative px-4 py-1.5 text-sm font-bold text-canvas transition hover:bg-negative/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-fg disabled:opacity-50"
      >
        {pending ? 'Deleting…' : 'Confirm'}
      </button>
      <button
        type="button"
        onClick={onCancel}
        disabled={pending}
        className="btn-secondary"
      >
        Cancel
      </button>
    </span>
  )
}
