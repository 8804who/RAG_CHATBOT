import { useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { Link } from 'react-router-dom'

import { useDeleteChat } from '../../hooks/useChat'
import { ApiError } from '../../lib/api/client'
import { formatDate } from '../../lib/format'
import type { ChatSummary } from '../../lib/types'
import { InlineConfirm } from '../InlineConfirm'

interface ChatListItemProps {
  chat: ChatSummary
  active: boolean
  onSelect: () => void
  onActiveDeleted: () => void
}

function deleteErrorText(err: Error): string {
  if (err instanceof ApiError && err.status === 409) {
    return 'Still answering in this chat. Delete it once the answer arrives.'
  }
  return "Couldn't delete this chat. Try again."
}

export function ChatListItem({
  chat,
  active,
  onSelect,
  onActiveDeleted,
}: ChatListItemProps): React.JSX.Element {
  const [confirming, setConfirming] = useState(false)
  const deleteButtonRef = useRef<HTMLButtonElement>(null)
  const remove = useDeleteChat(active ? chat.id : null, onActiveDeleted)
  const title = chat.title?.trim() || 'New chat'
  const when = chat.lastMessageAt ?? chat.createdAt

  return (
    <li>
      {confirming ? (
        <div className="rounded-md bg-surface-2 px-3 py-2">
          <p className="truncate text-sm">{title}</p>
          <InlineConfirm
            prompt="Delete?"
            pending={remove.isPending}
            onConfirm={() => remove.mutate(chat.id)}
            onCancel={() => {
              flushSync(() => setConfirming(false))
              deleteButtonRef.current?.focus()
            }}
          />
        </div>
      ) : (
        <div
          className={`flex items-center rounded-md transition ${
            active ? 'bg-surface-3' : 'hover:bg-surface-2'
          }`}
        >
          <Link
            to={`/chat/${encodeURIComponent(chat.id)}`}
            onClick={onSelect}
            aria-current={active ? 'page' : undefined}
            className="flex min-h-11 min-w-0 flex-1 flex-col justify-center rounded-md px-3 py-1.5 focus-visible:outline-2 focus-visible:outline-fg"
          >
            <span className={`truncate text-sm ${active ? 'font-bold text-fg' : 'text-soft'}`}>
              {title}
            </span>
            <time dateTime={when} className="text-xs text-muted">
              {formatDate(when)}
            </time>
          </Link>
          <button
            ref={deleteButtonRef}
            type="button"
            onClick={() => {
              remove.reset()
              setConfirming(true)
            }}
            aria-label={`Delete chat: ${title}`}
            className="grid size-11 shrink-0 place-items-center rounded-full text-muted transition hover:bg-surface-3 hover:text-negative focus-visible:outline-2 focus-visible:outline-fg"
          >
            <span aria-hidden>✕</span>
          </button>
        </div>
      )}
      {remove.error && (
        <p role="alert" className="px-3 pt-1 text-xs text-negative">
          {deleteErrorText(remove.error)}
        </p>
      )}
    </li>
  )
}
