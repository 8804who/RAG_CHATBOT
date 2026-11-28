import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { safeHttpUrl } from '../../lib/format'

interface MarkdownProps {
  content: string
}

// 렌더마다 새로 만들지 않도록 모듈 스코프에 둔다. raw HTML은 react-markdown 기본값대로 이스케이프된다.
const components: Components = {
  h1: ({ children }) => <h1 className="mt-4 mb-2 text-lg font-bold first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="mt-4 mb-2 text-base font-bold first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="mt-3 mb-1.5 font-bold first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="mt-3 mb-1.5 font-bold text-soft first:mt-0">{children}</h4>,
  p: ({ children }) => <p className="my-2 first:mt-0 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
  ol: ({ start, children }) => (
    <ol start={start} className="my-2 list-decimal space-y-1 pl-5">
      {children}
    </ol>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-2 border-l-2 border-line pl-3 text-muted">{children}</blockquote>
  ),
  // 외부 이미지 URL은 유출 경로가 될 수 있어 로드하지 않고 alt 텍스트만 남긴다.
  img: ({ alt }) => <>{alt}</>,
  hr: () => <hr className="my-3 border-line" />,
  a: ({ href, children }) => {
    const safe = safeHttpUrl(href)
    if (!safe) return <>{children}</>
    return (
      <a
        href={safe}
        target="_blank"
        rel="noopener noreferrer"
        className="text-fg underline decoration-line-strong underline-offset-2 hover:decoration-fg focus-visible:outline-2 focus-visible:outline-fg"
      >
        {children}
      </a>
    )
  },
  pre: ({ children }) => (
    <pre className="my-2 overflow-x-auto rounded-md bg-surface-3 p-3 text-xs [&>code]:bg-transparent [&>code]:p-0">
      {children}
    </pre>
  ),
  code: ({ className, children }) => (
    <code className={`rounded bg-surface-3 px-1 py-0.5 font-mono text-xs ${className ?? ''}`}>
      {children}
    </code>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="w-max min-w-full border-collapse text-left">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-line bg-surface-2 px-2 py-1 font-bold">{children}</th>
  ),
  td: ({ children }) => <td className="border border-line px-2 py-1">{children}</td>,
}

export function Markdown({ content }: MarkdownProps): React.JSX.Element {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  )
}
