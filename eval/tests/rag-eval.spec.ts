import fs from 'node:fs'
import path from 'node:path'

import { test, expect, request as playwrightRequest } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

import { createChat, sendMessage } from '../src/api'
import {
  clearTestSession,
  closeDb,
  getCollectionEmbedding,
  getIndexedDocuments,
  getLatestChatUsage,
  getToolCalls,
  seedTestSession,
} from '../src/db'
import type { IndexedDocument } from '../src/db'
import { judgeAnswer } from '../src/judge'
import { checkBehavior, computePrecision, computeRecall } from '../src/metrics'
import { DATASET_NAMES } from '../src/types'
import type { DatasetName, EvalCase, EvalResult } from '../src/types'

const DEFAULT_MIN_PRECISION = Number(process.env.MIN_PRECISION ?? 0.3)
const DEFAULT_MIN_RECALL = Number(process.env.MIN_RECALL ?? 1)
const DEFAULT_MIN_JUDGE_SCORE = Number(process.env.MIN_JUDGE_SCORE ?? 0.6)
const CHAT_MODEL = process.env.CHAT_MODEL || 'gpt-4o-mini'
const FIXTURES_DIR = path.resolve(__dirname, '..', process.env.EVAL_FIXTURES_DIR || 'fixtures/v2')

function selectedDatasets(): DatasetName[] {
  const raw = (process.env.EVAL_DATASET || 'all').split(',').map((s) => s.trim())
  if (raw.includes('all')) return [...DATASET_NAMES]
  const unknown = raw.filter((n) => !(DATASET_NAMES as readonly string[]).includes(n))
  if (unknown.length) {
    throw new Error(`EVAL_DATASET: unknown ${unknown.join(', ')} (use ${DATASET_NAMES.join(', ')} or all)`)
  }
  return raw as DatasetName[]
}

const cases: EvalCase[] = selectedDatasets().flatMap((name) => {
  const file = path.join(FIXTURES_DIR, `${name}.json`)
  const loaded = JSON.parse(fs.readFileSync(file, 'utf-8')) as EvalCase[]
  // File name is the source of truth; a mismatched `dataset` field would mislabel aggregates.
  return loaded.map((c) => ({ ...c, dataset: name }))
})

// Left undefined if beforeAll fails (e.g. Postgres unreachable) so afterAll
// can clean up whatever did get created without masking the real error.
let apiContext: APIRequestContext | undefined
let sessionToken: string | undefined
let indexedDocs: IndexedDocument[] = []

test.beforeAll(async () => {
  indexedDocs = await getIndexedDocuments()
  const session = await seedTestSession()
  sessionToken = session.token
  apiContext = await playwrightRequest.newContext({
    baseURL: process.env.API_BASE_URL ?? 'http://localhost:8000',
    extraHTTPHeaders: { Cookie: `session=${sessionToken}` },
  })
})

test.afterAll(async () => {
  await apiContext?.dispose()
  if (sessionToken) {
    await clearTestSession(sessionToken)
  }
  await closeDb()
})

/** Title → document_id; an unresolved or ambiguous title fails the case instead of scoring 0. */
function resolveDocumentIds(c: EvalCase): string[] {
  return c.expectedDocumentTitles.map((title) => {
    const ids = [
      ...new Set(
        indexedDocs
          .filter((d) => d.filename === title && (!c.collectionName || d.collection_name === c.collectionName))
          .map((d) => d.document_id),
      ),
    ]
    if (ids.length !== 1) {
      const where = c.collectionName ?? 'any collection'
      throw new Error(`expected document "${title}" resolved to ${ids.length} INDEXED documents in ${where}`)
    }
    return ids[0]
  })
}

function isRagCase(c: EvalCase): boolean {
  return c.expectedBehavior === 'answer_from_docs' || (!c.expectedBehavior && c.expectedDocumentTitles.length > 0)
}

for (const evalCase of cases) {
  test(`RAG eval [${evalCase.dataset}]: ${evalCase.id}`, async () => {
    // beforeAll has already run by this point (or the test is skipped entirely).
    if (!apiContext) throw new Error('apiContext was not initialized in beforeAll')
    const expectedDocumentIds = resolveDocumentIds(evalCase)

    const chatId = await createChat(apiContext, evalCase.collectionName, CHAT_MODEL)
    const { response, elapsedMs } = await sendMessage(apiContext, chatId, evalCase.query)

    // Citations = every chunk search_documents returned this turn (deduped), not only the ones the answer cites.
    const docCitations = response.citations.filter((c) => c.source_type === 'document')
    const retrievedDocumentIds = [...new Set(docCitations.flatMap((c) => c.document_id ?? []))]
    const retrievedChunkIds = docCitations.flatMap((c) => c.chunk_id ?? [])
    const recall = computeRecall(retrievedDocumentIds, expectedDocumentIds)
    const precision = computePrecision(retrievedDocumentIds, expectedDocumentIds)

    const usage = await getLatestChatUsage(chatId)
    if (!usage) {
      throw new Error(`no chat_usage_logs row found for conversation_id=${chatId}`)
    }
    const totalTokens = usage.input_tokens + usage.output_tokens + usage.reasoning_tokens

    const toolCalls = await getToolCalls(chatId)
    const behaviorFailures = checkBehavior(evalCase, toolCalls, response.content)
    const judged = await judgeAnswer(evalCase.query, evalCase.expectedAnswer, response.content, response.citations)

    const result: EvalResult = {
      id: evalCase.id,
      dataset: evalCase.dataset,
      query: evalCase.query,
      expectedBehavior: evalCase.expectedBehavior ?? null,
      expectedDocumentIds,
      retrievedDocumentIds,
      retrievedChunkIds,
      recall,
      precision,
      elapsedMs,
      inputTokens: usage.input_tokens,
      outputTokens: usage.output_tokens,
      reasoningTokens: usage.reasoning_tokens,
      totalTokens,
      citationCount: response.citations.length,
      judgeCorrectness: judged.correctness,
      judgeGroundedness: judged.groundedness,
      judgeVerdict: judged.verdict,
      judgeReasoning: judged.reasoning,
      behaviorFailures,
      answer: response.content,
      citations: response.citations,
      toolCalls,
    }
    // src/results-reporter.ts reads these two attachments to write eval/results/.
    await test.info().attach(`${evalCase.id}-metrics`, {
      body: JSON.stringify(result, null, 2),
      contentType: 'application/json',
    })
    await test.info().attach('run-context', {
      body: JSON.stringify({
        collection: evalCase.collectionName,
        chatModel: CHAT_MODEL,
        embedding: evalCase.collectionName ? await getCollectionEmbedding(evalCase.collectionName) : null,
        minPrecisionDefault: DEFAULT_MIN_PRECISION,
        minRecallDefault: DEFAULT_MIN_RECALL,
        minJudgeScoreDefault: DEFAULT_MIN_JUDGE_SCORE,
      }),
      contentType: 'application/json',
    })

    // Soft so one case reports every failed check, not just the first.
    expect.soft(behaviorFailures, `tool/behavior checks for "${evalCase.query}"`).toEqual([])
    if (isRagCase(evalCase)) {
      expect.soft(recall ?? 0, `retrieval recall for "${evalCase.query}"`).toBeGreaterThanOrEqual(
        evalCase.minRecall ?? DEFAULT_MIN_RECALL,
      )
      expect.soft(precision ?? 0, `retrieval precision for "${evalCase.query}"`).toBeGreaterThanOrEqual(
        evalCase.minPrecision ?? DEFAULT_MIN_PRECISION,
      )
    }
    expect
      .soft(judged.correctness, `LLM-judge correctness for "${evalCase.query}" — ${judged.reasoning}`)
      .toBeGreaterThanOrEqual(evalCase.minJudgeScore ?? DEFAULT_MIN_JUDGE_SCORE)
  })
}
