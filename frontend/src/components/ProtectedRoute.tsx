import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

export function ProtectedRoute(): React.JSX.Element {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted">
        Loading…
      </div>
    )
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />
}
