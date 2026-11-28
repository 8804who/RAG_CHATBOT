export interface SseEvent {
  event: string
  data: string
}

// One frame (the text between blank lines). Comment-only frames yield null.
function parseFrame(frame: string): SseEvent | null {
  let event = 'message'
  const data: string[] = []
  for (const line of frame.split('\n')) {
    if (line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') event = value
    else if (field === 'data') data.push(value)
  }
  return data.length > 0 ? { event, data: data.join('\n') } : null
}

/**
 * Incremental text/event-stream reader (EventSource can't POST). Frames may be
 * split across chunks; an unterminated frame at EOF is dropped, as the spec says.
 * Stopping iteration early cancels the body, closing the connection.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseEvent> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      // Normalized on the whole buffer so a CRLF split across chunks still joins.
      buffer = (buffer + decoder.decode(value, { stream: !done })).replaceAll('\r\n', '\n')
      let end = buffer.indexOf('\n\n')
      while (end !== -1) {
        const parsed = parseFrame(buffer.slice(0, end))
        buffer = buffer.slice(end + 2)
        if (parsed) yield parsed
        end = buffer.indexOf('\n\n')
      }
      if (done) return
    }
  } finally {
    reader.cancel().catch(() => undefined)
  }
}
