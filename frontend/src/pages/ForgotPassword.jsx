import { useState } from 'react'
import { Link } from 'react-router-dom'
import { authAPI } from '../services/api'
import { useToast } from '../context/ToastContext'
import ThemeToggle from '../components/ThemeToggle'

function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [resendLoading, setResendLoading] = useState(false)
  const [sentEmail, setSentEmail] = useState(null)
  const toast = useToast()

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authAPI.forgotPassword({ email })
      setSentEmail(email)
      toast.success('If that email is registered, we sent reset instructions.')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not send reset email')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (!sentEmail) return
    setError('')
    setResendLoading(true)
    try {
      await authAPI.forgotPassword({ email: sentEmail })
      toast.success('If that email is registered, we sent reset instructions.')
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not resend email')
    } finally {
      setResendLoading(false)
    }
  }

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
          {sentEmail ? (
            <div className="text-center">
              <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-indigo-600 shadow-md shadow-indigo-600/25">
                <svg className="h-8 w-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.75}
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-slate-50">
                Check your email
              </h2>
              <p className="mt-4 text-base text-gray-700 dark:text-slate-300 leading-relaxed">
                If an account exists for <strong className="text-gray-900 dark:text-slate-100">{sentEmail}</strong>, we
                sent a password reset link.
              </p>
              <p className="mt-3 text-sm text-gray-600 dark:text-slate-400 leading-relaxed max-w-sm mx-auto">
                Open the link to choose a new password. You might need to{' '}
                <strong className="text-gray-800 dark:text-slate-300">check your spam folder</strong>.
              </p>

              {error && (
                <div className="mt-5 flex items-center justify-center gap-2 rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-left text-sm text-red-600 dark:text-red-400">
                  <svg className="h-4 w-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  {error}
                </div>
              )}

              <div className="mt-8 flex flex-col items-center gap-4 sm:flex-row sm:justify-center sm:gap-6">
                <button
                  type="button"
                  disabled={resendLoading}
                  onClick={handleResend}
                  className="w-full sm:w-auto min-w-[180px] rounded-xl bg-indigo-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-500 disabled:opacity-60 disabled:pointer-events-none"
                >
                  {resendLoading ? (
                    <span className="inline-flex items-center justify-center gap-2">
                      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                      </svg>
                      Sending…
                    </span>
                  ) : (
                    'Resend email'
                  )}
                </button>
                <Link
                  to="/"
                  className="inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300"
                >
                  Return to Site
                  <span aria-hidden>→</span>
                </Link>
              </div>

              <p className="mt-10 text-xs text-gray-400 dark:text-slate-500 max-w-md mx-auto">
                If you have any questions, contact your administrator or IT support.
              </p>
            </div>
          ) : (
            <>
              <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100 mb-2">Forgot password</h2>
              <p className="text-sm text-gray-500 dark:text-slate-400 mb-6">
                Enter your email and we will send you a link to reset your password.
              </p>

              <form className="space-y-5" onSubmit={submit}>
                {error && (
                  <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm">
                    <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    {error}
                  </div>
                )}

                <div>
                  <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">
                    Email address
                  </label>
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="input-field"
                    placeholder="you@example.com"
                    autoComplete="email"
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
                      Sending…
                    </>
                  ) : (
                    'Send reset link'
                  )}
                </button>
              </form>

              <div className="mt-6 text-center">
                <Link
                  to="/login"
                  className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300"
                >
                  Back to sign in
                </Link>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default ForgotPassword
