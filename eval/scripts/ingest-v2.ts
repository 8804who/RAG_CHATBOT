// Ingests test-data/v2/*.md into rag_eval_v2 through the real API and waits
// until every file is INDEXED. Idempotent: reuses the collection if it exists
// and skips filenames already INDEXED (or still in flight) there.
// Run from eval/: `npm run ingest:v2` (API + ingest worker must be running).
import fs from 'node:fs'
import path from 'node:path'

import dotenv from 'dotenv'

import { clearTestSession, closeDb, getDocumentStatuses, seedTestSession } from '../src/db.ts'

dotenv.config({ path: '.env', quiet: true })

const BASE = process.env.API_BASE_URL ?? 'http://localhost:8000'
const TARGET = 'rag_eval_v2'
const SOURCE = 'rag_eval_papers' // embedding config is copied from here; never modified
const DOCS_DIR = path.resolve('test-data/v2')
const DESCRIPTION =
  '2025-2026 news events: Korean presidential/local elections, APEC 2025 Gyeongju, KBO 2025, ' +
  'Yeongnam wildfire 2025, papal conclave 2025, Ballon d\'Or 2025/2026, FIFA World Cup 2026, Winter Olympics 2026'
const TIMEOUT_MS = 10 * 60 * 1000

async function api(cookie: string, method: string, url: string, body?: unknown): Promise<Response> {
  return fetch(`${BASE}/api/v1${url}`, {
    method,
    headers: { Cookie: `session=${cookie}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

async function ensureCollection(cookie: string): Promise<void> {
  if ((await api(cookie, 'GET', `/collections/${TARGET}`)).ok) return
  const src = await api(cookie, 'GET', `/collections/${SOURCE}`)
  if (!src.ok) throw new Error(`GET ${SOURCE} failed: ${src.status} ${await src.text()}`)
  const detail = (await src.json()) as {
    dense_vectors: Record<string, { size: number; distance: string; on_disk: boolean }>
    sparse_vectors: Record<string, { modifier: string | null; on_disk: boolean }>
    embedding_model: string | null
  }
  if (!detail.embedding_model) throw new Error(`${SOURCE} has no embedding_model`)
  const dims = Object.values(detail.dense_vectors).map((v) => v.size)
  const res = await api(cookie, 'POST', '/collections', {
    collection_name: TARGET,
    dense_vectors: detail.dense_vectors,
    sparse_vectors: Object.fromEntries(
      Object.entries(detail.sparse_vectors).map(([k, v]) => [k, { modifier: v.modifier ?? 'none', on_disk: v.on_disk }]),
    ),
    embedding_model: { name: detail.embedding_model, dimension: dims[0] },
    description: DESCRIPTION,
  })
  if (!res.ok) throw new Error(`create ${TARGET} failed: ${res.status} ${await res.text()}`)
  console.log(`created ${TARGET} (${detail.embedding_model}, dim ${dims[0]})`)
}

async function main(): Promise<void> {
  const files = fs.readdirSync(DOCS_DIR).filter((f) => f.endsWith('.md')).sort()
  const { token } = await seedTestSession()
  try {
    await ensureCollection(token)
    const existing = await getDocumentStatuses(TARGET)
    for (const filename of files) {
      const statuses = existing.filter((d) => d.filename === filename).map((d) => d.status)
      // FAILED-only rows get a fresh upload; anything else is done or in flight.
      if (statuses.some((s) => s !== 'FAILED')) {
        console.log(`skip ${filename} (${statuses.join(',')})`)
        continue
      }
      const content = fs.readFileSync(path.join(DOCS_DIR, filename), 'utf-8')
      const res = await api(token, 'POST', `/collections/${TARGET}/documents`, { filename, content })
      if (!res.ok) throw new Error(`upload ${filename} failed: ${res.status} ${await res.text()}`)
      console.log(`uploaded ${filename}`)
    }

    const deadline = Date.now() + TIMEOUT_MS
    for (;;) {
      const rows = await getDocumentStatuses(TARGET)
      const indexed = new Set(rows.filter((r) => r.status === 'INDEXED').map((r) => r.filename))
      const pending = files.filter((f) => !indexed.has(f))
      if (pending.length === 0) break
      // Only fail on a file with no live (non-FAILED) row left.
      const failed = pending.filter((f) => rows.filter((r) => r.filename === f).every((r) => r.status === 'FAILED'))
      if (failed.length) throw new Error(`ingest FAILED: ${failed.join(', ')}`)
      if (Date.now() > deadline) throw new Error(`timed out waiting for: ${pending.join(', ')}`)
      console.log(`waiting: ${indexed.size}/${files.length} INDEXED`)
      await new Promise((r) => setTimeout(r, 3000))
    }
    console.log(`all ${files.length} documents INDEXED in ${TARGET}`)
  } finally {
    await clearTestSession(token)
    await closeDb()
  }
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
