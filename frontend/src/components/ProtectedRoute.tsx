import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

export default function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-gray-400">
        Loading…
      </div>
    )
  }

  return user ? <Outlet /> : <Navigate to="/login" replace />
}
