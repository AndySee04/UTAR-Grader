import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authAPI } from '../services/api'
import { useToast } from '../context/ToastContext'
import ThemeToggle from '../components/ThemeToggle'

function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [message, setMessage] = useState('')
  const toast = useToast()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('Passwords do not match')
      return
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters')
      return
    }
    if (!token || !String(token).trim()) {
      setError('Missing reset link. Open the link from your email.')
      return
    }

    setLoading(true)
    try {
      const res = await authAPI.resetPassword({
        token: String(token).trim(),
        new_password: password,
      })
      setMessage(res.data.message || 'Your password has been updated.')
      setDone(true)
      toast.success('Password updated')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not reset password')
    } finally {
      setLoading(false)
    }
  }

  const missingToken = !token || !String(token).trim()

  return (
    <div className="auth-bg relative flex flex-col justify-center py-12 sm:px-6 lg:px-8 min-h-screen">
      <div className="absolute top-4 right-4 z-20">
        <ThemeToggle variant="onHero" />
      </div>
      <div className="relative z-10 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex flex-col items-center mb-8">
          <img
            src="/logo/utar-grader-logo.png"
            alt="UTAR Grader logo"
            className="w-14 h-14 object-contain mb-4 drop-shadow-md"
          />
          <h1 className="text-3xl font-extrabold tracking-[0.12em] text-white">UTAR GRADER</h1>
          <p className="mt-2 text-indigo-200/70 text-sm">AI-Powered Exam Grading</p>
        </div>

        <div className="auth-card py-8 px-6 sm:px-10">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100 mb-4">Set a new password</h2>

          {done ? (
            <div className="space-y-4">
              <div className="flex items-start gap-2 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 px-4 py-3 rounded-xl text-sm">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <div>
                  <p className="font-medium">{message}</p>
                </div>
              </div>
              <Link
                to="/login"
                className="inline-flex w-full justify-center btn-primary py-3 text-center font-medium"
              >
                Continue to sign in
              </Link>
            </div>
          ) : missingToken ? (
            <div className="space-y-4">
              <div className="flex items-start gap-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Missing reset link. Use the link from your email or request a new one.</span>
              </div>
              <Link to="/forgot-password" className="inline-flex w-full justify-center btn-primary py-3 text-center font-medium">
                Request reset link
              </Link>
              <Link
                to="/login"
                className="inline-flex w-full justify-center py-2 text-sm font-medium text-indigo-600 dark:text-indigo-400"
              >
                Back to sign in
              </Link>
            </div>
          ) : (
            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && (
                <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm">
                  <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">
                  New password
                </label>
                <input
                  id="new-password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input-field"
                  placeholder="••••••••"
                  autoComplete="new-password"
                />
                <p className="mt-1 text-xs text-gray-400 dark:text-slate-500">Minimum 6 characters</p>
              </div>

              <div>
                <label htmlFor="confirm-password" className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">
                  Confirm new password
                </label>
                <input
                  id="confirm-password"
                  type="password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="input-field"
                  placeholder="••••••••"
                  autoComplete="new-password"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full btn-primary py-3 flex justify-center items-center gap-2"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Updating…
                  </>
                ) : (
                  'Update password'
                )}
              </button>

              <div className="text-center">
                <Link to="/login" className="text-sm font-medium text-indigo-600 dark:text-indigo-400">
                  Back to sign in
                </Link>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}

export default ResetPassword
