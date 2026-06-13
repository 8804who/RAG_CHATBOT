import type { ChatMessage } from '../../lib/types'

export default function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-2xl ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${
            isUser
              ? 'bg-brand-500 text-white'
              : 'border border-gray-200 bg-white text-gray-800'
          }`}
        >
          {message.content}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="mt-2 space-y-1.5">
            <p className="text-xs font-medium text-gray-400">Sources</p>
            {message.citations.map((c, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2 text-xs text-gray-600"
              >
                <p className="font-medium text-gray-700">📄 {c.documentName}</p>
                <p className="mt-0.5 italic">{c.snippet}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
