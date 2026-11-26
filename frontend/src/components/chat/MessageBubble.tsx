import type { ChatMessage } from '../../lib/types'

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-2xl ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`whitespace-pre-wrap rounded-lg px-4 py-3 text-sm leading-normal ${
            isUser
              ? 'bg-surface-3 text-fg'
              : 'bg-surface text-fg'
          }`}
        >
          {message.content}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-xs font-bold text-muted">Sources</p>
            {message.citations.map((c, i) => (
              <div
                key={c.sourceType === 'web' ? (c.url ?? i) : (c.chunkId ?? i)}
                className="rounded-md bg-surface-2 px-3 py-2 text-xs text-muted"
              >
                {c.sourceType === 'web' ? (
                  c.url ? (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-bold text-fg hover:underline"
                    >
                      🌐 {c.title}
                    </a>
                  ) : (
                    <p className="font-bold text-fg">🌐 {c.title}</p>
                  )
                ) : (
                  <p className="font-bold text-fg">
                    📄 {c.title}
                    {c.collectionName && (
                      <span className="ml-1.5 rounded-full bg-surface-4 px-1.5 py-0.5 text-2xs font-normal text-soft">
                        {c.collectionName}
                      </span>
                    )}
                  </p>
                )}
                <p className="mt-0.5 italic">{c.snippet}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
