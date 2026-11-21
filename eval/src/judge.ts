import OpenAI from 'openai'

import type { Citation, JudgeVerdict } from './types'

// Stronger than the chat models under test (gpt-4o-mini / gpt-4o) so the grader
// isn't grading itself. Source: developers.openai.com/api/docs/models.
const DEFAULT_JUDGE_MODEL = 'gpt-6.2-sol'

export function judgeModel(): string {
  return process.env.JUDGE_MODEL || DEFAULT_JUDGE_MODEL
}

const JUDGE_SYSTEM_PROMPT =
  'You are a strict grader for a RAG chatbot evaluation. Score two things separately.\n' +
  "correctness (0.0-1.0): the chatbot's answer vs. the reference answer, given the question. " +
  'Paraphrasing, other languages, and omitted secondary detail are fine; wrong facts, wrong ' +
  'numbers, or missing the core claim are not. If the reference says the information is not ' +
  'available, an answer that says so is correct and a confident made-up answer is incorrect.\n' +
  'groundedness (0.0-1.0): the fraction of the answer\'s factual claims that are supported by the ' +
  'retrieved context, ignoring the reference answer. Claims from general knowledge not in the ' +
  'context count as unsupported. If the answer makes no factual claims (greeting, refusal, ' +
  'pure arithmetic), score 1.0.'

const JUDGE_RESPONSE_SCHEMA = {
  type: 'json_schema' as const,
  json_schema: {
    name: 'judge_verdict',
    strict: true,
    schema: {
      type: 'object',
      properties: {
        correctness: { type: 'number', description: '0.0 (wrong) to 1.0 (fully correct)' },
        verdict: { type: 'string', enum: ['correct', 'partially_correct', 'incorrect'] },
        groundedness: { type: 'number', description: '0.0 (unsupported) to 1.0 (fully supported)' },
        reasoning: { type: 'string', description: 'Two or three sentences covering both scores' },
      },
      required: ['correctness', 'verdict', 'groundedness', 'reasoning'],
      additionalProperties: false,
    },
  },
}

let client: OpenAI | undefined

function getClient(): OpenAI {
  if (!client) {
    const apiKey = process.env.OPENAI_API_KEY
    if (!apiKey) {
      throw new Error('OPENAI_API_KEY is required for LLM-as-judge scoring (set it in eval/.env)')
    }
    client = new OpenAI({ apiKey })
  }
  return client
}

/**
 * Context = citation snippets, which are exactly the 300-char chunk prefixes the
 * agent saw in its tool output (backend tools.py _chunks_to_json), so
 * groundedness is judged against what the model actually had.
 */
function formatContext(citations: Citation[]): string {
  if (citations.length === 0) return '(nothing retrieved)'
  return citations
    .map((c, i) => `[${i + 1}] ${c.title}${c.url ? ` <${c.url}>` : ''}\n${c.snippet}`)
    .join('\n\n')
}

export async function judgeAnswer(
  question: string,
  referenceAnswer: string,
  actualAnswer: string,
  citations: Citation[],
): Promise<JudgeVerdict> {
  const model = judgeModel()
  const response = await getClient().chat.completions.create({
    model,
    messages: [
      { role: 'system', content: JUDGE_SYSTEM_PROMPT },
      {
        role: 'user',
        content:
          `Question: ${question}\n\nReference answer: ${referenceAnswer}\n\n` +
          `Retrieved context:\n${formatContext(citations)}\n\nChatbot's answer: ${actualAnswer}`,
      },
    ],
    response_format: JUDGE_RESPONSE_SCHEMA,
  })

  const raw = response.choices[0]?.message?.content
  if (!raw) {
    throw new Error(`judge model '${model}' returned no content`)
  }
  return JSON.parse(raw) as JudgeVerdict
}
