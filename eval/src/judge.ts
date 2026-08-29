import OpenAI from 'openai'

import type { JudgeVerdict } from './types'

const JUDGE_SYSTEM_PROMPT =
  "You are a strict grader for a RAG chatbot evaluation. Compare the chatbot's answer to " +
  'the reference answer for factual correctness and completeness, given the question. ' +
  'Paraphrasing, different wording, and omitted secondary detail are fine; wrong facts, ' +
  'wrong numbers, or missing the core claim are not. Score continuously from 0.0 (wrong) ' +
  'to 1.0 (fully correct and complete).'

const JUDGE_RESPONSE_SCHEMA = {
  type: 'json_schema' as const,
  json_schema: {
    name: 'judge_verdict',
    strict: true,
    schema: {
      type: 'object',
      properties: {
        score: {
          type: 'number',
          description: '0.0 (completely wrong) to 1.0 (fully correct and complete)',
        },
        verdict: {
          type: 'string',
          enum: ['correct', 'partially_correct', 'incorrect'],
        },
        reasoning: {
          type: 'string',
          description: 'One or two sentences explaining the score',
        },
      },
      required: ['score', 'verdict', 'reasoning'],
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

export async function judgeAnswer(
  question: string,
  referenceAnswer: string,
  actualAnswer: string,
): Promise<JudgeVerdict> {
  const model = process.env.JUDGE_MODEL ?? 'gpt-4o-mini'
  const response = await getClient().chat.completions.create({
    model,
    messages: [
      { role: 'system', content: JUDGE_SYSTEM_PROMPT },
      {
        role: 'user',
        content: `Question: ${question}\n\nReference answer: ${referenceAnswer}\n\nChatbot's answer: ${actualAnswer}`,
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
