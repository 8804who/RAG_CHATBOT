import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import ChatPage from './pages/ChatPage'
import CollectionsPage from './pages/CollectionsPage'
import DocumentsPage from './pages/DocumentsPage'
import LoginPage from './pages/LoginPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="/collections" element={<CollectionsPage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to="/chat" replace />} />
    </Routes>
  )
}
