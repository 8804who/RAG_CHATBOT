import { useChatList } from '../../hooks/useChat'
import { ChatListItem } from './ChatListItem'

interface ChatListPanelProps {
  activeChatId: string | null
  onNewChat: () => void
  // Clicking an item; navigation itself happens through its link.
  onSelect: () => void
}

export function ChatListPanel({
  activeChatId,
  onNewChat,
  onSelect,
}: ChatListPanelProps): React.JSX.Element {
  const list = useChatList()

  function renderList(): React.JSX.Element {
    if (list.isPending) {
      return (
        <p role="status" className="px-3 text-sm text-muted">
          Loading chats…
        </p>
      )
    }
    if (list.isError) {
      return (
        <div role="alert" className="px-3 text-sm text-negative">
          <p>Couldn't load your chats.</p>
          <button type="button" onClick={() => void list.refetch()} className="btn-secondary mt-2">
            Retry
          </button>
        </div>
      )
    }
    if (list.data.length === 0) {
      return <p className="px-3 text-sm text-muted">No chats yet. Ask a question to start one.</p>
    }
    return (
      <ul className="space-y-1">
        {list.data.map((c) => (
          <ChatListItem
            key={c.id}
            chat={c}
            active={c.id === activeChatId}
            onSelect={onSelect}
            onActiveDeleted={onNewChat}
          />
        ))}
      </ul>
    )
  }

  return (
    <nav aria-label="Chats" className="flex min-h-0 flex-1 flex-col">
      <div className="p-3">
        <button type="button" onClick={onNewChat} className="btn-secondary w-full">
          New chat
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">{renderList()}</div>
    </nav>
  )
}
