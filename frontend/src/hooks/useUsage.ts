import { useQuery } from '@tanstack/react-query'

import { getUsageStats } from '../lib/api/usage'

export function useUsageStats() {
  return useQuery({
    queryKey: ['usage', 'stats'],
    queryFn: getUsageStats,
    staleTime: 60 * 1000,
  })
}
