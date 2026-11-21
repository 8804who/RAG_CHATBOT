import { execSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

import type { FullResult, Reporter, TestCase, TestResult } from '@playwright/test/reporter'

import { judgeModel } from './judge'
import type { CaseRecord, EvalResult } from './types'

const EVAL_DIR = path.join(__dirname, '..')
const CONSTANTS_PATH = path.join(EVAL_DIR, '../backend/app/core/constants.py')

// Reads `NAME = <int>` from backend constants so the record reflects what the
// backend actually ran with, without importing Python.
function readBackendConstant(source: string, name: string): number | null {
  const match = source.match(new RegExp(`^${name}\\s*=\\s*(\\d+)`, 'm'))
  return match ? Number(match[1]) : null
}

function gitSha(): string {
  try {
    const sha = execSync('git rev-parse --short HEAD', { cwd: EVAL_DIR }).toString().trim()
    const dirty = execSync('git status --porcelain', { cwd: EVAL_DIR }).toString().trim()
    return dirty ? `${sha}-dirty` : sha
  } catch {
    return 'unknown'
  }
}

function percentile(sorted: number[], p: number): number | null {
  if (sorted.length === 0) return null
  // Nearest-rank: small case counts make interpolation pointless.
  return sorted[Math.min(sorted.length - 1, Math.ceil((p / 100) * sorted.length) - 1)]
}

function mean(values: number[]): number | null {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null
}

// Verified in backend services/agent/agent_orchestrator.py _extract_citations.
const CITATION_SEMANTICS =
  'citations = every chunk returned by search_documents this turn (deduped by chunk_id) plus web/arXiv results; ' +
  'not only the sources the answer cites. Snippets are the 300-char chunk prefix the agent saw.'

interface RunContext {
  datasets: string[]
  datasetSize: number
  chatModels: string[]
  collections: string[]
  embedding: { model: string; dimension: number } | null
  minPrecisionDefault: number | null
  minRecallDefault: number | null
  minJudgeScoreDefault: number | null
}

interface CaseContext {
  collection: string | null
  chatModel: string
  embedding: { model: string; dimension: number } | null
  minPrecisionDefault: number
  minRecallDefault: number
  minJudgeScoreDefault: number
}

const present = (values: (number | null)[]): number[] => values.filter((v): v is number => v !== null)

function aggregate(records: CaseRecord[]) {
  const results = records.flatMap((r) => r.result ?? [])
  const latencies = results.map((r) => r.elapsedMs).sort((a, b) => a - b)
  const precisions = present(results.map((r) => r.precision))
  return {
    cases: records.length,
    casesRecorded: results.length,
    casesErrored: records.length - results.length,
    passCount: records.filter((r) => r.status === 'passed').length,
    meanRecall: mean(present(results.map((r) => r.recall))),
    meanPrecision: mean(precisions),
    minPrecision: precisions.length ? Math.min(...precisions) : null,
    meanCorrectness: mean(results.map((r) => r.judgeCorrectness)),
    meanGroundedness: mean(results.map((r) => r.judgeGroundedness)),
    behaviorPassRate: mean(results.map((r) => (r.behaviorFailures.length === 0 ? 1 : 0))),
    meanInputTokens: mean(results.map((r) => r.inputTokens)),
    meanOutputTokens: mean(results.map((r) => r.outputTokens)),
    meanTotalTokens: mean(results.map((r) => r.totalTokens)),
    meanToolCalls: mean(results.map((r) => r.toolCalls.length)),
    latencyP50Ms: percentile(latencies, 50),
    latencyP95Ms: percentile(latencies, 95),
  }
}

const fmt = (v: number | null, d = 2) => (v === null ? '-' : Number.isInteger(v) ? String(v) : v.toFixed(d))
const cell = (s: string) => s.replace(/\|/g, '\\|').replace(/\n/g, ' ')

/** Tool sequence as `name(args)` in call order, e.g. `search_documents({"query":"..."}) → calculate(...)`. */
function toolSequence(r: EvalResult): string {
  return r.toolCalls.map((t) => `${t.tool_name}(${JSON.stringify(t.tool_args ?? {})})`).join(' → ') || '(none)'
}

function writeResults(records: CaseRecord[], ctx: RunContext): string[] {
  const label = process.env.EVAL_LABEL ?? 'baseline'
  const now = new Date()
  const date = now.toISOString().slice(0, 10)
  const constants = fs.existsSync(CONSTANTS_PATH) ? fs.readFileSync(CONSTANTS_PATH, 'utf-8') : ''

  const meta = {
    date: now.toISOString(),
    label,
    gitSha: gitSha(),
    datasets: ctx.datasets,
    chatModels: ctx.chatModels,
    judgeModel: judgeModel(),
    judgeContext: 'citation snippets (what the agent saw)',
    citationSemantics: CITATION_SEMANTICS,
    embeddingModel: ctx.embedding?.model ?? null,
    embeddingDimension: ctx.embedding?.dimension ?? null,
    collections: ctx.collections,
    retrievalTopK: readBackendConstant(constants, 'DEFAULT_RETRIEVAL_TOP_K'),
    chunkSizeWords: readBackendConstant(constants, 'DEFAULT_CHUNK_SIZE'),
    chunkOverlapWords: readBackendConstant(constants, 'DEFAULT_CHUNK_OVERLAP'),
    agentRecursionLimit: readBackendConstant(constants, 'AGENT_RECURSION_LIMIT'),
    datasetSize: ctx.datasetSize,
    minPrecisionDefault: ctx.minPrecisionDefault,
    minRecallDefault: ctx.minRecallDefault,
    minJudgeScoreDefault: ctx.minJudgeScoreDefault,
  }
  const datasets = [...new Set(records.map((r) => r.dataset))]
  const byDataset = Object.fromEntries(
    datasets.map((d) => [d, aggregate(records.filter((r) => r.dataset === d))]),
  )
  const aggregates = aggregate(records)

  const outDir = path.join(EVAL_DIR, 'results')
  fs.mkdirSync(outDir, { recursive: true })
  const base = path.join(outDir, `${date}-${label}`)
  fs.writeFileSync(
    `${base}.json`,
    JSON.stringify({ meta, aggregates, aggregatesByDataset: byDataset, cases: records }, null, 2),
  )

  const aggKeys = Object.keys(aggregates) as (keyof typeof aggregates)[]
  const lines = [
    `# RAG eval: ${label} (${date})`,
    '',
    '## Run',
    '',
    ...Object.entries(meta).map(([k, v]) => `- ${k}: ${Array.isArray(v) ? v.join(', ') : v}`),
    '',
    '## Aggregates by dataset',
    '',
    `|metric|${datasets.join('|')}|all|`,
    `|---|${datasets.map(() => '---').join('|')}|---|`,
    ...aggKeys.map(
      (k) => `|${k}|${datasets.map((d) => fmt(byDataset[d][k], 3)).join('|')}|${fmt(aggregates[k], 3)}|`,
    ),
    '',
    '## Cases',
    '',
    '|dataset|id|status|recall|precision|correct|grounded|behavior|in_tok|out_tok|latency_ms|citations (doc_id:count)|',
    '|---|---|---|---|---|---|---|---|---|---|---|---|',
    ...records.map((r) => {
      const x = r.result
      if (!x) return `|${r.dataset}|${r.id}|${r.status}|-|-|-|-|-|-|-|-|error: ${cell(r.errors.join(' / '))}|`
      const byDoc = new Map<string, number>()
      for (const c of x.citations) {
        const key = c.document_id?.slice(0, 8) ?? 'web'
        byDoc.set(key, (byDoc.get(key) ?? 0) + 1)
      }
      const docs = [...byDoc].map(([id, n]) => `${id}:${n}`).join(' ')
      const behavior = x.behaviorFailures.length ? cell(x.behaviorFailures.join('; ')) : 'ok'
      return `|${r.dataset}|${r.id}|${r.status}|${fmt(x.recall)}|${fmt(x.precision)}|${fmt(x.judgeCorrectness)}|${fmt(x.judgeGroundedness)}|${behavior}|${x.inputTokens}|${x.outputTokens}|${x.elapsedMs}|${docs}|`
    }),
    '',
    '## Tool sequences',
    '',
    ...records.map((r) => `- **${r.dataset}/${r.id}**: ${r.result ? cell(toolSequence(r.result)) : '(errored)'}`),
    '',
    '## Judge reasoning',
    '',
    ...records.flatMap((r) =>
      r.result
        ? [`- **${r.dataset}/${r.id}** (correct ${fmt(r.result.judgeCorrectness)}, grounded ${fmt(r.result.judgeGroundedness)}): ${r.result.judgeReasoning}`]
        : [],
    ),
    '',
    'Citations carry no retrieval score: the chat API does not return one. Full answers and citations are in the JSON.',
    '',
  ]
  fs.writeFileSync(`${base}.md`, lines.join('\n'))
  return [`${base}.json`, `${base}.md`]
}

function readAttachment<T>(result: TestResult, name: string): T | undefined {
  const body = result.attachments.find((a) => a.name === name)?.body
  return body ? (JSON.parse(body.toString()) as T) : undefined
}

/**
 * Writes eval/results/<date>-<EVAL_LABEL>.{json,md}. Lives in a reporter (main
 * process) because Playwright restarts the worker after every failed test,
 * which wipes any module-level state a spec's afterAll could aggregate.
 */
const TITLE_RE = /^RAG eval \[([^\]]+)\]: (.+)$/

export default class ResultsReporter implements Reporter {
  private readonly records: CaseRecord[] = []
  private readonly contexts: CaseContext[] = []
  private datasetSize = 0

  onBegin(_config: unknown, suite: { allTests(): TestCase[] }): void {
    this.datasetSize = suite.allTests().filter((t) => TITLE_RE.test(t.title)).length
  }

  onTestEnd(test: TestCase, result: TestResult): void {
    const match = TITLE_RE.exec(test.title)
    if (!match) return // unit specs (tests/*.unit.spec.ts) are not eval cases
    const [, dataset, id] = match
    const context = readAttachment<CaseContext>(result, 'run-context')
    if (context) this.contexts.push(context)
    this.records.push({
      id,
      dataset,
      status: result.status,
      errors: result.errors.map((e) => e.message ?? String(e)),
      result: readAttachment<EvalResult>(result, `${id}-metrics`),
    })
  }

  onEnd(_result: FullResult): void {
    if (this.records.length === 0) return
    const first = this.contexts[0]
    console.table(
      this.records.map((r) => ({
        dataset: r.dataset,
        id: r.id,
        status: r.status,
        recall: r.result ? fmt(r.result.recall) : '-',
        precision: r.result ? fmt(r.result.precision) : '-',
        correct: r.result ? fmt(r.result.judgeCorrectness) : '-',
        grounded: r.result ? fmt(r.result.judgeGroundedness) : '-',
        behavior: r.result ? (r.result.behaviorFailures.length ? 'FAIL' : 'ok') : '-',
        tools: r.result ? r.result.toolCalls.map((t) => t.tool_name).join('>') : '-',
        time_ms: r.result?.elapsedMs ?? '-',
        total_tok: r.result?.totalTokens ?? '-',
      })),
    )
    const files = writeResults(this.records, {
      datasets: [...new Set(this.records.map((r) => r.dataset))],
      datasetSize: this.datasetSize,
      chatModels: [...new Set(this.contexts.map((c) => c.chatModel))],
      collections: [...new Set(this.contexts.map((c) => c.collection ?? '(agent-routed)'))],
      embedding: this.contexts.find((c) => c.embedding)?.embedding ?? null,
      minPrecisionDefault: first?.minPrecisionDefault ?? null,
      minRecallDefault: first?.minRecallDefault ?? null,
      minJudgeScoreDefault: first?.minJudgeScoreDefault ?? null,
    })
    console.log(`eval results written: ${files.join(', ')}`)
  }
}
