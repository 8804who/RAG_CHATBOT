import { Navigate, Route, Routes } from 'react-router-dom'

import { Layout } from './components/Layout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { ChatPage } from './pages/ChatPage'
import { CollectionsPage } from './pages/CollectionsPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { LoginPage } from './pages/LoginPage'
import { MyPage } from './pages/MyPage'

export function App(): React.JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          {/* One optional-segment route so /chat -> /chat/:id (first message) keeps the page mounted. */}
          <Route path="/chat/:chatId?" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/collections" element={<CollectionsPage />} />
          <Route path="/my" element={<MyPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  )
}
