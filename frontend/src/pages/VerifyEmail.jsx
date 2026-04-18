import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { authAPI } from '../services/api'
import ThemeToggle from '../components/ThemeToggle'

function VerifyEmail() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState('loading')
  const [message, setMessage] = useState('')
  const [email, setEmail] = useState('')

  useEffect(() => {
    if (!token || !String(token).trim()) {
      setStatus('error')
      setMessage('Missing verification link. Use the link from your email or register again.')
      return
    }

    let cancelled = false
    ;(async () => {
      try {
        const res = await authAPI.verifyEmail(String(token).trim())
        if (cancelled) return
        setStatus('ok')
        setMessage(res.data.message)
        setEmail(res.data.email || '')
      } catch (err) {
        if (cancelled) return
        setStatus('error')
        setMessage(err.response?.data?.detail || 'Verification failed.')
      }
    })()

    return () => {
      cancelled = true
    }
  }, [token])

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
          <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100 mb-4">
            Email verification
          </h2>

          {status === 'loading' && (
            <div className="flex items-center gap-3 text-gray-600 dark:text-slate-300">
              <svg className="animate-spin h-5 w-5 text-indigo-500" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Verifying your email…
            </div>
          )}

          {status === 'ok' && (
            <div className="space-y-4">
              <div className="flex items-start gap-2 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-300 px-4 py-3 rounded-xl text-sm">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <div>
                  <p className="font-medium">{message}</p>
                  {email && (
                    <p className="mt-1 text-emerald-700/90 dark:text-emerald-400/90 text-xs">{email}</p>
                  )}
                </div>
              </div>
              <Link
                to="/login?verified=1"
                className="inline-flex w-full justify-center btn-primary py-3 text-center font-medium"
              >
                Continue to sign in
              </Link>
            </div>
          )}

          {status === 'error' && (
            <div className="space-y-4">
              <div className="flex items-start gap-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm">
                <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>{message}</span>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
                <Link
                  to="/register"
                  className="inline-flex justify-center btn-primary py-3 text-center font-medium"
                >
                  Register again
                </Link>
                <Link
                  to="/login"
                  className="inline-flex justify-center py-3 text-center text-sm font-medium text-indigo-600 dark:text-indigo-400"
                >
                  Back to sign in
                </Link>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default VerifyEmail
