export const DATASET_NAMES = ['ko-rag', 'en-rag', 'ko-nonrag', 'en-nonrag', 'tool'] as const
export type DatasetName = (typeof DATASET_NAMES)[number]

export type ExpectedBehavior = 'answer_from_docs' | 'no_search' | 'web_search' | 'not_in_docs'

/** One tool-argument expectation: some call of `tool` must have `arg` matching. */
export interface ExpectedArg {
  tool: string
  arg: string
  /** Compared as strings, so 42 matches "42". */
  equals?: string | number
  /** The arg is an arithmetic expression that must evaluate to this number. */
  evaluatesTo?: number
}

/** One case in fixtures/v2/<dataset>.json. */
export interface EvalCase {
  id: string
  dataset: DatasetName
  lang: 'ko' | 'en'
  query: string
  /** null = the chat is created unpinned and the agent picks the collection. */
  collectionName: string | null
  /** Document filenames; resolved to document_ids at run start (document_progress_status). */
  expectedDocumentTitles: string[]
  /** Reference answer the chatbot's actual answer is graded against by the LLM judge. */
  expectedAnswer: string
  sourceUrls: string[]
  expectedBehavior?: ExpectedBehavior
  expectedTools?: string[]
  forbiddenTools?: string[]
  expectedArgs?: ExpectedArg[]
  maxToolCalls?: number
  /** Overrides MIN_JUDGE_SCORE (correctness) for this case. */
  minJudgeScore?: number
  /** Overrides MIN_RECALL for this case (RAG cases only). */
  minRecall?: number
  /** Overrides MIN_PRECISION for this case (RAG cases only). */
  minPrecision?: number
}

export interface JudgeVerdict {
  /** 0.0-1.0: actual answer vs. reference answer. */
  correctness: number
  verdict: 'correct' | 'partially_correct' | 'incorrect'
  /** 0.0-1.0: are the answer's claims supported by the retrieved context. */
  groundedness: number
  reasoning: string
}

export interface Citation {
  source_type: 'document' | 'web'
  title: string
  snippet: string
  document_id?: string
  chunk_id?: string
  collection_name?: string
  url?: string
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

export interface ToolCallRow {
  tool_name: string
  tool_args: Record<string, unknown> | null
}

export interface EvalResult {
  id: string
  dataset: DatasetName
  query: string
  expectedBehavior: ExpectedBehavior | null
  expectedDocumentIds: string[]
  /** Distinct document_ids / chunk_ids over every search_documents result this turn. */
  retrievedDocumentIds: string[]
  retrievedChunkIds: string[]
  /** null when the case has no expected documents. */
  recall: number | null
  precision: number | null
  elapsedMs: number
  inputTokens: number
  outputTokens: number
  reasoningTokens: number
  totalTokens: number
  citationCount: number
  judgeCorrectness: number
  judgeGroundedness: number
  judgeVerdict: JudgeVerdict['verdict']
  judgeReasoning: string
  /** Tool / behavior assertion failures; empty = all passed. */
  behaviorFailures: string[]
  answer: string
  citations: Citation[]
  /** Agent tool calls for this turn in call order, from agent_tool_call_logs. */
  toolCalls: ToolCallRow[]
}

/** One case as written to eval/results/; result is absent if the case errored before scoring. */
export interface CaseRecord {
  id: string
  dataset: string
  status: string
  errors: string[]
  result?: EvalResult
}
