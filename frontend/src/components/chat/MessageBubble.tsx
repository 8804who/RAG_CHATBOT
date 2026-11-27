import { safeHttpUrl } from '../../lib/format'
import type { Citation, ChatMessage } from '../../lib/types'

interface MessageBubbleProps {
  message: ChatMessage
}

function citationKey(c: Citation, i: number): string {
  return `${c.sourceType}-${c.chunkId ?? c.url ?? c.title}-${i}`
}

export function MessageBubble({ message }: MessageBubbleProps): React.JSX.Element {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className="max-w-2xl">
        <div
          className={`whitespace-pre-wrap rounded-lg px-4 py-3 text-sm leading-normal text-fg ${
            isUser ? 'bg-surface-3' : 'bg-surface'
          }`}
        >
          {message.content}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-xs font-bold text-muted">Sources</p>
            {message.citations.map((c, i) => {
              const isWeb = c.sourceType === 'web'
              const href = isWeb ? safeHttpUrl(c.url) : undefined
              return (
                <div
                  key={citationKey(c, i)}
                  className="rounded-md bg-surface-2 px-3 py-2 text-xs text-muted"
                >
                  <p className="font-bold text-fg">
                    <span aria-hidden="true">{isWeb ? '🌐' : '📄'} </span>
                    <span className="mr-1.5 rounded-full bg-surface-4 px-1.5 py-0.5 text-2xs font-normal text-soft">
                      {isWeb ? 'Web' : 'Your documents'}
                    </span>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="hover:underline focus-visible:outline-2 focus-visible:outline-fg"
                      >
                        {c.title}
                      </a>
                    ) : (
                      c.title
                    )}
                    {c.collectionName && (
                      <span className="ml-1.5 rounded-full bg-surface-4 px-1.5 py-0.5 text-2xs font-normal text-soft">
                        {c.collectionName}
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 italic">{c.snippet}</p>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
