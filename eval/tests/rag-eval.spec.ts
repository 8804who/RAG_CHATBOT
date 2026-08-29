import fs from 'node:fs'
import path from 'node:path'

import { test, expect, request as playwrightRequest } from '@playwright/test'
import type { APIRequestContext } from '@playwright/test'

import { createChat, sendMessage } from '../src/api'
import { clearTestSession, closeDb, getLatestChatUsage, seedTestSession } from '../src/db'
import { judgeAnswer } from '../src/judge'
import { computePrecision } from '../src/metrics'
import type { EvalResult, GoldenCase } from '../src/types'

const DEFAULT_MIN_PRECISION = Number(process.env.MIN_PRECISION ?? 0.5)
const DEFAULT_MIN_JUDGE_SCORE = Number(process.env.MIN_JUDGE_SCORE ?? 0.6)

const cases: GoldenCase[] = JSON.parse(
  fs.readFileSync(path.join(__dirname, '../fixtures/golden-dataset.json'), 'utf-8'),
)

// Left undefined if beforeAll fails (e.g. Postgres unreachable) so afterAll
// can clean up whatever did get created without masking the real error.
let apiContext: APIRequestContext | undefined
let sessionToken: string | undefined
const results: EvalResult[] = []

test.beforeAll(async () => {
  const session = await seedTestSession()
  sessionToken = session.token
  apiContext = await playwrightRequest.newContext({
    baseURL: process.env.API_BASE_URL ?? 'http://localhost:8000',
    extraHTTPHeaders: { Cookie: `session=${sessionToken}` },
  })
})

test.afterAll(async () => {
  if (results.length > 0) {
    console.table(
      results.map((r) => ({
        id: r.id,
        precision: r.precision.toFixed(2),
        judge: r.judgeScore.toFixed(2),
        verdict: r.judgeVerdict,
        time_ms: r.elapsedMs,
        total_tok: r.totalTokens,
        citations: r.citationCount,
      })),
    )
  }
  await apiContext?.dispose()
  if (sessionToken) {
    await clearTestSession(sessionToken)
  }
  await closeDb()
})

for (const goldenCase of cases) {
  test(`RAG eval: ${goldenCase.id}`, async () => {
    // beforeAll has already run by this point (or the test is skipped entirely).
    if (!apiContext) throw new Error('apiContext was not initialized in beforeAll')
    const chatId = await createChat(apiContext, goldenCase.collectionName, goldenCase.chatModel)
    const { response, elapsedMs } = await sendMessage(apiContext, chatId, goldenCase.query)

    const retrievedDocumentIds = response.citations.map((citation) => citation.document_id)
    const precision = computePrecision(retrievedDocumentIds, goldenCase.expectedDocumentIds)

    const usage = await getLatestChatUsage(chatId)
    if (!usage) {
      throw new Error(`no chat_usage_logs row found for conversation_id=${chatId}`)
    }
    const totalTokens = usage.input_tokens + usage.output_tokens + usage.reasoning_tokens

    const judged = await judgeAnswer(goldenCase.query, goldenCase.expectedAnswer, response.content)

    const result: EvalResult = {
      id: goldenCase.id,
      query: goldenCase.query,
      precision,
      elapsedMs,
      inputTokens: usage.input_tokens,
      outputTokens: usage.output_tokens,
      reasoningTokens: usage.reasoning_tokens,
      totalTokens,
      citationCount: retrievedDocumentIds.length,
      judgeScore: judged.score,
      judgeVerdict: judged.verdict,
      judgeReasoning: judged.reasoning,
    }
    results.push(result)
    await test.info().attach(`${goldenCase.id}-metrics`, {
      body: JSON.stringify({ ...result, actualAnswer: response.content }, null, 2),
      contentType: 'application/json',
    })

    expect(precision, `retrieval precision for "${goldenCase.query}"`).toBeGreaterThanOrEqual(
      goldenCase.minPrecision ?? DEFAULT_MIN_PRECISION,
    )
    expect(
      judged.score,
      `LLM-judge score for "${goldenCase.query}" — ${judged.reasoning}`,
    ).toBeGreaterThanOrEqual(goldenCase.minJudgeScore ?? DEFAULT_MIN_JUDGE_SCORE)
    if (goldenCase.maxElapsedMs !== undefined) {
      expect(elapsedMs, `response time for "${goldenCase.query}"`).toBeLessThanOrEqual(
        goldenCase.maxElapsedMs,
      )
    }
    if (goldenCase.maxTotalTokens !== undefined) {
      expect(totalTokens, `token usage for "${goldenCase.query}"`).toBeLessThanOrEqual(
        goldenCase.maxTotalTokens,
      )
    }
  })
}
