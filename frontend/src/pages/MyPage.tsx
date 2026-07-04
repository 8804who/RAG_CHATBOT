import { useAuth } from '../auth/AuthContext'
import { useUsageStats } from '../hooks/useUsage'
import type { ChatUsageStat, EmbeddingUsageStat } from '../lib/types'

function formatTokens(value: number): string {
  return value.toLocaleString()
}

function formatCost(cost: number | null, currency: string | null): string {
  if (cost === null) return '—'
  return `${currency ?? 'USD'} ${cost.toFixed(4)}`
}

interface EmbeddingTableProps {
  rows: EmbeddingUsageStat[]
}

function EmbeddingUsageTable({ rows }: EmbeddingTableProps): React.JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[36rem] text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs uppercase tracking-wide text-gray-500">
            <th className="px-5 py-3 font-medium">Model</th>
            <th className="px-5 py-3 text-right font-medium">Documents</th>
            <th className="px-5 py-3 text-right font-medium">Tokens</th>
            <th className="px-5 py-3 text-right font-medium">Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.model} className="border-b border-gray-50 last:border-0">
              <td className="px-5 py-3 font-medium text-gray-900">{row.model}</td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-600">
                {formatTokens(row.document_count)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-600">
                {formatTokens(row.total_tokens)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-900">
                {formatCost(row.cost, row.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface ChatTableProps {
  rows: ChatUsageStat[]
}

function ChatUsageTable({ rows }: ChatTableProps): React.JSX.Element {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[48rem] text-sm">
        <thead>
          <tr className="border-b border-gray-100 text-left text-xs uppercase tracking-wide text-gray-500">
            <th className="px-5 py-3 font-medium">Model</th>
            <th className="px-5 py-3 text-right font-medium">Messages</th>
            <th className="px-5 py-3 text-right font-medium">Input</th>
            <th className="px-5 py-3 text-right font-medium">Output</th>
            <th className="px-5 py-3 text-right font-medium">Reasoning</th>
            <th className="px-5 py-3 text-right font-medium">Total</th>
            <th className="px-5 py-3 text-right font-medium">Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.model} className="border-b border-gray-50 last:border-0">
              <td className="px-5 py-3 font-medium text-gray-900">{row.model}</td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-600">
                {formatTokens(row.message_count)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-600">
                {formatTokens(row.input_tokens)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-600">
                {formatTokens(row.output_tokens)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-600">
                {formatTokens(row.reasoning_tokens)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-900">
                {formatTokens(row.total_tokens)}
              </td>
              <td className="px-5 py-3 text-right tabular-nums text-gray-900">
                {formatCost(row.cost, row.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

interface UsageCardProps {
  title: string
  subtitle: string
  isEmpty: boolean
  emptyLabel: string
  children: React.ReactNode
}

function UsageCard({
  title,
  subtitle,
  isEmpty,
  emptyLabel,
  children,
}: UsageCardProps): React.JSX.Element {
  return (
    <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
      <div className="border-b border-gray-100 px-5 py-3">
        <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
        <p className="text-xs text-gray-500">{subtitle}</p>
      </div>
      {isEmpty ? (
        <p className="px-5 py-8 text-center text-sm text-gray-400">{emptyLabel}</p>
      ) : (
        children
      )}
    </div>
  )
}

export default function MyPage(): React.JSX.Element {
  const { user } = useAuth()
  const { data, isLoading, isError } = useUsageStats()

  return (
    <div className="flex h-full flex-col">
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <h1 className="text-lg font-semibold">My usage</h1>
        <p className="text-sm text-gray-500">
          Token usage and estimated cost for {user?.email ?? 'your account'},
          grouped by model.
        </p>
      </header>

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {isLoading && (
            <p className="text-sm text-gray-500">Loading usage…</p>
          )}
          {isError && (
            <p className="text-sm text-red-600">
              Could not load usage stats. Please try again.
            </p>
          )}

          {data && (
            <>
              <div className="rounded-2xl border border-gray-200 bg-white px-6 py-5">
                <p className="text-xs uppercase tracking-wide text-gray-500">
                  Total estimated cost
                </p>
                <p className="mt-1 text-3xl font-semibold tabular-nums text-gray-900">
                  {data.currency} {data.total_cost.toFixed(4)}
                </p>
                <p className="mt-1 text-xs text-gray-400">
                  Cost shows “—” for models without configured pricing.
                </p>
              </div>

              <UsageCard
                title="Embedding (ingestion)"
                subtitle="Tokens spent embedding uploaded documents."
                isEmpty={data.embedding.length === 0}
                emptyLabel="No documents ingested yet."
              >
                <EmbeddingUsageTable rows={data.embedding} />
              </UsageCard>

              <UsageCard
                title="Chat"
                subtitle="Input, output, and reasoning tokens spent on chat."
                isEmpty={data.chat.length === 0}
                emptyLabel="No chat usage recorded yet."
              >
                <ChatUsageTable rows={data.chat} />
              </UsageCard>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
