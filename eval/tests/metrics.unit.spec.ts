import { test, expect } from '@playwright/test'

import { checkBehavior, computePrecision, computeRecall, evaluateArithmetic } from '../src/metrics'
import type { EvalCase } from '../src/types'

// Pure-logic checks: no API, DB, or LLM. The results reporter ignores these by title.

test('evaluateArithmetic follows Python precedence and rejects non-arithmetic', () => {
  expect(evaluateArithmetic('(3 + 4) * 2 - 10 / 4')).toBe(11.5)
  expect(evaluateArithmetic('-2**2')).toBe(-4)
  expect(evaluateArithmetic('2**-1')).toBe(0.5)
  expect(evaluateArithmetic('7 // 2 + -7 % 3')).toBe(5)
  expect(evaluateArithmetic('1.5e3 * .5')).toBe(750)
  for (const bad of ['process.exit()', '2 ^ 3', '1,000 + 1', '(1 + 2', '1 +', '']) {
    expect(() => evaluateArithmetic(bad), bad).toThrow()
  }
})

test('recall and precision are document-level and null without expectations', () => {
  expect(computeRecall(['a', 'b'], ['a', 'c'])).toBe(0.5)
  expect(computePrecision(['a', 'b', 'b'], ['a'])).toBe(0.5)
  expect(computePrecision([], ['a'])).toBe(0)
  expect(computeRecall(['a'], [])).toBeNull()
  expect(computePrecision(['a'], [])).toBeNull()
})

test('checkBehavior reports each failed tool and behavior rule', () => {
  const base: EvalCase = {
    id: 'x', dataset: 'tool', lang: 'en', query: 'q', collectionName: null,
    expectedDocumentTitles: [], expectedAnswer: 'a', sourceUrls: [],
  }
  const calls = [
    { tool_name: 'search_documents', tool_args: { query: 'q' } },
    { tool_name: 'calculate', tool_args: { expression: '12 * (3 + 4)' } },
  ]
  expect(
    checkBehavior({ ...base, expectedTools: ['calculate'], expectedArgs: [{ tool: 'calculate', arg: 'expression', evaluatesTo: 84 }] }, calls, ''),
  ).toEqual([])
  const failures = checkBehavior(
    {
      ...base,
      expectedBehavior: 'no_search',
      expectedTools: ['tavily_search'],
      forbiddenTools: ['calculate'],
      expectedArgs: [{ tool: 'calculate', arg: 'expression', evaluatesTo: 85 }],
      maxToolCalls: 1,
    },
    calls,
    '',
  )
  expect(failures).toHaveLength(5)
  expect(checkBehavior({ ...base, expectedBehavior: 'not_in_docs' }, calls, 'It says so [1].')).toHaveLength(1)
  expect(checkBehavior({ ...base, expectedBehavior: 'not_in_docs' }, calls, 'Not in the documents.')).toEqual([])
})
