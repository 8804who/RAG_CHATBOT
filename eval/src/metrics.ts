import type { EvalCase, ToolCallRow } from './types'

const RETRIEVAL_TOOL = 'search_documents'
const WEB_TOOLS = ['tavily_search', 'arxiv_search']

/**
 * Retrieval precision = distinct relevant document_ids retrieved / distinct document_ids retrieved.
 * null when the case expects no documents (nothing to measure against).
 */
export function computePrecision(retrieved: string[], expected: string[]): number | null {
  if (expected.length === 0) return null
  const docs = [...new Set(retrieved)]
  if (docs.length === 0) return 0
  const want = new Set(expected)
  return docs.filter((id) => want.has(id)).length / docs.length
}

/** Document-level recall@k = expected docs found among the k retrieved chunks / expected docs. */
export function computeRecall(retrieved: string[], expected: string[]): number | null {
  if (expected.length === 0) return null
  const got = new Set(retrieved)
  const want = [...new Set(expected)]
  return want.filter((id) => got.has(id)).length / want.length
}

/**
 * Evaluates a plain arithmetic expression (numbers, + - * / // % **, parentheses)
 * with a recursive-descent parser — never eval(). Mirrors Python/simpleeval
 * precedence (-2**2 = -4). Throws on anything else (names, ^, commas).
 */
export function evaluateArithmetic(expression: string): number {
  const tokens = expression.match(/\d+(?:\.\d+)?(?:e[+-]?\d+)?|\.\d+|\*\*|\/\/|[-+*/%()]|\S/gi) ?? []
  let pos = 0
  const peek = () => tokens[pos]
  const next = () => tokens[pos++]

  const atom = (): number => {
    const tok = next()
    if (tok === '(') {
      const value = expr()
      if (next() !== ')') throw new Error(`missing ')' in "${expression}"`)
      return value
    }
    if (tok !== undefined && /^(\d|\.\d)/.test(tok)) return Number(tok)
    throw new Error(`unexpected token "${tok ?? 'end'}" in "${expression}"`)
  }
  const power = (): number => {
    const base = atom()
    if (peek() === '**') {
      next()
      return base ** unary()
    }
    return base
  }
  const unary = (): number => {
    if (peek() === '-') {
      next()
      return -unary()
    }
    if (peek() === '+') {
      next()
      return unary()
    }
    return power()
  }
  const term = (): number => {
    let value = unary()
    for (let op = peek(); op === '*' || op === '/' || op === '//' || op === '%'; op = peek()) {
      next()
      const rhs = unary()
      if (op === '*') value *= rhs
      else if (op === '/') value /= rhs
      else if (op === '//') value = Math.floor(value / rhs)
      else value = value - rhs * Math.floor(value / rhs) // Python modulo sign
    }
    return value
  }
  const expr = (): number => {
    let value = term()
    for (let op = peek(); op === '+' || op === '-'; op = peek()) {
      next()
      value = op === '+' ? value + term() : value - term()
    }
    return value
  }

  const value = expr()
  if (pos !== tokens.length) throw new Error(`trailing input in "${expression}"`)
  return value
}

function argMatches(value: unknown, equals?: string | number, evaluatesTo?: number): boolean {
  if (value === undefined || value === null) return false
  if (equals !== undefined && String(value) !== String(equals)) return false
  if (evaluatesTo !== undefined) {
    try {
      const got = evaluateArithmetic(String(value))
      if (Math.abs(got - evaluatesTo) > 1e-9 * Math.max(1, Math.abs(evaluatesTo))) return false
    } catch {
      return false
    }
  }
  return true
}

/** Tool/behavior assertions for one case; returns human-readable failures (empty = pass). */
export function checkBehavior(c: EvalCase, toolCalls: ToolCallRow[], answer: string): string[] {
  const failures: string[] = []
  const called = new Set(toolCalls.map((t) => t.tool_name))

  for (const tool of c.expectedTools ?? []) {
    if (!called.has(tool)) failures.push(`expected tool "${tool}" was not called`)
  }
  for (const tool of c.forbiddenTools ?? []) {
    if (called.has(tool)) failures.push(`forbidden tool "${tool}" was called`)
  }
  for (const e of c.expectedArgs ?? []) {
    const ok = toolCalls.some(
      (t) => t.tool_name === e.tool && argMatches(t.tool_args?.[e.arg], e.equals, e.evaluatesTo),
    )
    if (!ok) failures.push(`no ${e.tool} call with ${e.arg} matching ${JSON.stringify(e)}`)
  }
  if (c.maxToolCalls !== undefined && toolCalls.length > c.maxToolCalls) {
    failures.push(`${toolCalls.length} tool calls > maxToolCalls ${c.maxToolCalls}`)
  }
  if (c.expectedBehavior === 'no_search' && called.has(RETRIEVAL_TOOL)) {
    failures.push(`no_search case called ${RETRIEVAL_TOOL}`)
  }
  if (c.expectedBehavior === 'web_search' && !WEB_TOOLS.some((t) => called.has(t))) {
    failures.push(`web_search case called none of ${WEB_TOOLS.join(', ')}`)
  }
  // The API returns every retrieved chunk as a citation, so the fabrication
  // signal is the answer itself: [n] markers claim document support that isn't there.
  // shortcut: [n] next to a web search is assumed to cite the web result; check per-marker if that proves loose.
  const usedWeb = WEB_TOOLS.some((t) => called.has(t))
  if (c.expectedBehavior === 'not_in_docs' && !usedWeb && /\[\d+\]/.test(answer)) {
    failures.push('not_in_docs answer cites document sources with [n] markers')
  }
  return failures
}
