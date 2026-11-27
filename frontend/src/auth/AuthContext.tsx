import { useQueryClient } from '@tanstack/react-query'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import { getCurrentUser, logout as apiLogout, startLogin } from '../lib/api/auth'
import type { User } from '../lib/types'

interface AuthContextValue {
  user: User | null
  loading: boolean
  login: () => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({
  children,
}: {
  children: ReactNode
}): React.JSX.Element {
  const queryClient = useQueryClient()
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCurrentUser()
      .then(setUser)
      .finally(() => setLoading(false))
  }, [])

  const login = useCallback(async () => {
    await startLogin()
    setUser(await getCurrentUser())
  }, [])

  // Clear every cached query so the next user in this tab never sees the
  // previous user's data, even if the logout request itself failed.
  const logout = useCallback(async () => {
    try {
      await apiLogout()
    } finally {
      queryClient.clear()
      setUser(null)
    }
  }, [queryClient])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
