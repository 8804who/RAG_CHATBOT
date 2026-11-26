import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

const navItems = [
  { to: '/chat', label: 'Chat', icon: '💬' },
  { to: '/documents', label: 'Documents', icon: '📄' },
  { to: '/collections', label: 'Collections', icon: '▤' },
  { to: '/my', label: 'My usage', icon: '📊' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full bg-canvas text-fg">
      <aside className="flex w-64 shrink-0 flex-col bg-surface">
        <div className="flex items-center gap-2 px-5 py-5">
          <span className="grid size-8 place-items-center rounded-lg bg-surface-3 text-fg">
            ◆
          </span>
          <span className="text-lg font-bold">RAG Chatbot</span>
        </div>

        <nav className="flex-1 space-y-1 px-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2 text-sm transition focus-visible:outline-2 focus-visible:outline-fg ${
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
          <button
            type="button"
            onClick={handleLogout}
            className="btn-ghost mt-1 w-full"
          >
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <Outlet />
      </main>
    </div>
  )
}
