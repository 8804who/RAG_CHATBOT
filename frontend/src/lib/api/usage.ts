import type { UsageStatsResponse } from '../types'
import { apiFetch } from './client'

// The /usage/stats route exists on the backend, so there is no mock branch.

export async function getUsageStats(): Promise<UsageStatsResponse> {
  return apiFetch<UsageStatsResponse>('/api/v1/usage/stats')
}
