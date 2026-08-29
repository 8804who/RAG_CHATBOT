import crypto from 'node:crypto'

import { Pool } from 'pg'

import type { ChatUsageRow } from './types'

// Bypasses Google OAuth for the eval run: Playwright can't complete a real
// Google consent screen headlessly, so we seed a User + GoogleSession row
// directly (same tables the real OAuth callback writes to) and send that
// session token as a cookie.
const TEST_GOOGLE_SUB = 'rag-eval-playwright'
const TEST_EMAIL = 'rag-eval@playwright.local'
const SESSION_TTL_MS = 60 * 60 * 1000

export interface TestSession {
  userId: number
  token: string
}

let pool: Pool | null = null

function getPool(): Pool {
  if (!pool) {
    pool = new Pool({
      host: process.env.POSTGRES_HOST ?? 'localhost',
      port: Number(process.env.POSTGRES_PORT ?? 5432),
      user: process.env.POSTGRES_USER,
      password: process.env.POSTGRES_PASSWORD,
      database: process.env.POSTGRES_DB,
    })
  }
  return pool
}

export async function seedTestSession(): Promise<TestSession> {
  const db = getPool()
  const userResult = await db.query<{ id: number }>(
    `INSERT INTO users (google_sub, email, name, picture)
     VALUES ($1, $2, 'RAG Eval Bot', NULL)
     ON CONFLICT (google_sub) DO UPDATE SET email = EXCLUDED.email
     RETURNING id`,
    [TEST_GOOGLE_SUB, TEST_EMAIL],
  )
  const userId = userResult.rows[0].id

  const token = crypto.randomUUID()
  const expiresAt = new Date(Date.now() + SESSION_TTL_MS)
  await db.query(
    `INSERT INTO google_sessions (token, user_id, expires_at) VALUES ($1, $2, $3)`,
    [token, userId, expiresAt],
  )

  return { userId, token }
}

export async function clearTestSession(token: string): Promise<void> {
  const db = getPool()
  await db.query(`DELETE FROM google_sessions WHERE token = $1`, [token])
}

/**
 * ChatOrchestrator.send_message writes this row (keyed by conversation_id =
 * chat_id) synchronously before the HTTP response is returned, so it's
 * already committed by the time sendMessage()'s await resolves.
 */
export async function getLatestChatUsage(conversationId: string): Promise<ChatUsageRow | null> {
  const db = getPool()
  const result = await db.query<ChatUsageRow>(
    `SELECT input_tokens, output_tokens, reasoning_tokens
     FROM chat_usage_logs
     WHERE conversation_id = $1
     ORDER BY created_at DESC, id DESC
     LIMIT 1`,
    [conversationId],
  )
  return result.rows[0] ?? null
}

export async function closeDb(): Promise<void> {
  if (pool) {
    await pool.end()
    pool = null
  }
}
