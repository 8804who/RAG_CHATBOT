export interface GoldenCase {
  id: string
  query: string
  collectionName: string
  chatModel: string
  /** Golden relevant document_ids for this query; precision is measured against these. */
  expectedDocumentIds: string[]
  /** Reference answer the chatbot's actual answer is graded against by the LLM judge. */
  expectedAnswer: string
  /** Overrides MIN_PRECISION for this case. */
  minPrecision?: number
  /** Overrides MIN_JUDGE_SCORE for this case. */
  minJudgeScore?: number
  /** Latency budget in ms; left unset, elapsed time is recorded but not asserted. */
  maxElapsedMs?: number
  /** Token budget (input + output + reasoning); left unset, recorded but not asserted. */
  maxTotalTokens?: number
}

export interface JudgeVerdict {
  score: number
  verdict: 'correct' | 'partially_correct' | 'incorrect'
  reasoning: string
}

export interface Citation {
  chunk_id: string
  document_id: string
  filename: string
  snippet: string
}

export interface ChatMessageApiResponse {
  role: string
  content: string
  citations: Citation[]
}

export interface ChatUsageRow {
  input_tokens: number
  output_tokens: number
  reasoning_tokens: number
}

export interface EvalResult {
  id: string
  query: string
  precision: number
  elapsedMs: number
  inputTokens: number
  outputTokens: number
  reasoningTokens: number
  totalTokens: number
  citationCount: number
  judgeScore: number
  judgeVerdict: JudgeVerdict['verdict']
  judgeReasoning: string
}
