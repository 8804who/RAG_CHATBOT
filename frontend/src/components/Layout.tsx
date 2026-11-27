import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

// Paths must match the routes in App.tsx.
const navItems = [
  { to: '/chat', label: 'Chat', icon: '💬' },
  { to: '/documents', label: 'Documents', icon: '📄' },
  { to: '/collections', label: 'Collections', icon: '▤' },
  { to: '/my', label: 'My usage', icon: '📊' },
]

const iconButtonClass =
  'grid size-11 place-items-center rounded-full text-muted transition hover:bg-surface-3 hover:text-fg focus-visible:outline-2 focus-visible:outline-fg'

export function Layout(): React.JSX.Element {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  // The drawer (below md) is open only for the path it was opened on, so any
  // route change closes it without an effect.
  const [openOnPath, setOpenOnPath] = useState<string | null>(null)
  const drawerOpen = openOnPath === pathname

  useEffect(() => {
    if (!drawerOpen) return
    function handleKeyDown(e: KeyboardEvent): void {
      if (e.key !== 'Escape') return
      setOpenOnPath(null)
      menuButtonRef.current?.focus()
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [drawerOpen])

  return (
    <div className="flex h-full flex-col bg-canvas text-fg md:flex-row">
      <header className="flex shrink-0 items-center gap-2 bg-surface px-2 py-1 md:hidden">
        <button
          ref={menuButtonRef}
          type="button"
          onClick={() => setOpenOnPath(drawerOpen ? null : pathname)}
          aria-expanded={drawerOpen}
          aria-controls="app-sidebar"
          aria-label={drawerOpen ? 'Close navigation' : 'Open navigation'}
          className={iconButtonClass}
        >
          <span aria-hidden>☰</span>
        </button>
        <span className="text-lg font-bold">RAG Chatbot</span>
      </header>

      {drawerOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
          onClick={() => setOpenOnPath(null)}
          aria-hidden
        />
      )}

      <aside
        id="app-sidebar"
        className={`${drawerOpen ? 'flex' : 'hidden'} fixed inset-y-0 left-0 z-40 w-64 flex-col bg-surface md:static md:flex md:shrink-0`}
      >
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="grid size-8 place-items-center rounded-lg bg-surface-3 text-fg">
            ◆
          </span>
          <span className="flex-1 text-lg font-bold">RAG Chatbot</span>
          <button
            type="button"
            onClick={() => setOpenOnPath(null)}
            aria-label="Close navigation"
            className={`${iconButtonClass} -mr-3 md:hidden`}
          >
            <span aria-hidden>✕</span>
          </button>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              // Same-page links don't change pathname, so close explicitly.
              onClick={() => setOpenOnPath(null)}
              className={({ isActive }) =>
                `flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-sm transition focus-visible:outline-2 focus-visible:outline-fg ${
                  isActive
                    ? 'bg-surface-3 font-bold text-fg'
                    : 'text-muted hover:text-fg'
                }`
              }
            >
              <span aria-hidden>{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-canvas p-3">
          <div className="flex items-center gap-3 px-2 py-2">
            {user?.picture ? (
              <img
                src={user.picture}
                alt=""
                className="size-8 rounded-full object-cover"
              />
            ) : (
              <span className="grid size-8 place-items-center rounded-full bg-surface-3 text-sm font-bold">
                {(user?.name ?? user?.email ?? '?')[0]?.toUpperCase()}
              </span>
            )}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold">
                {user?.name ?? 'User'}
              </p>
              <p className="truncate text-xs text-muted">{user?.email}</p>
            </div>
          </div>
          {/* Clearing the user makes ProtectedRoute redirect to /login. */}
          <button
            type="button"
            onClick={() => void logout()}
            className="btn-ghost mt-1 w-full"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex min-h-0 min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
