import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import GradePaper from './pages/GradePaper'
import ExamList from './pages/ExamList'
import ExamResults from './pages/ExamResults'
import ManageAccount from './pages/ManageAccount'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }
  
  if (!user) {
    return <Navigate to="/login" replace />
  }
  
  return children
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/" element={
        <ProtectedRoute>
          <Dashboard />
        </ProtectedRoute>
      }>
        <Route index element={<Navigate to="/grade" replace />} />
        <Route path="grade" element={<GradePaper />} />
        <Route path="exams" element={<ExamList />} />
        <Route path="exams/:examId/results" element={<ExamResults />} />
        <Route path="account" element={<ManageAccount />} />
      </Route>
    </Routes>
  )
}

export default App
