import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import GradePaper from './pages/GradePaper'
import ExamList from './pages/ExamList'
import ExamResults from './pages/ExamResults'
import ManageAccount from './pages/ManageAccount'
import CaptureSession from './pages/CaptureSession'
import VerifyEmail from './pages/VerifyEmail'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50/50 dark:bg-slate-950">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 dark:border-indigo-400"></div>
      </div>
    )
  }

  if (!user) {
    const next = encodeURIComponent(`${location.pathname}${location.search}`)
    return <Navigate to={`/login?next=${next}`} replace />
  }

  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/verify-email" element={<VerifyEmail />} />
      <Route path="/capture/:sessionId" element={<CaptureSession />} />
      <Route path="/" element={
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="/exams" replace />} />
        <Route path="grade" element={<GradePaper />} />
        <Route path="exams" element={<ExamList />} />
        <Route path="exams/:examId/results" element={<ExamResults />} />
        <Route path="account" element={<ManageAccount />} />
      </Route>
    </Routes>
  )
}

export default App
