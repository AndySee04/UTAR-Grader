import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import ThemeToggle from '../components/ThemeToggle'
import { isValidEmail } from '../utils/validation'
import { sanitizeNext } from '../utils/navigation'

function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login, user, loading: authLoading } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const nextAfterLogin = sanitizeNext(searchParams.get('next'))
  const verifiedToastShown = useRef(false)

  useEffect(() => {
    if (authLoading) return
    if (user && nextAfterLogin) navigate(nextAfterLogin, { replace: true })
  }, [authLoading, user, nextAfterLogin, navigate])

  useEffect(() => {
    if (verifiedToastShown.current) return
    if (searchParams.get('verified') !== '1') return
    verifiedToastShown.current = true
    toast.success('Email verified. You can sign in.')
    const sp = new URLSearchParams()
    if (nextAfterLogin) sp.set('next', nextAfterLogin)
    const q = sp.toString()
    navigate(q ? `/login?${q}` : '/login', { replace: true })
  }, [searchParams, navigate, toast, nextAfterLogin])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (!isValidEmail(email)) {
      setError('Please enter a valid email address')
      return
    }
    setLoading(true)

    try {
      await login(email.trim(), password)
      toast.success('Welcome back!')
      const dest = nextAfterLogin || '/'
      navigate(dest)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to login')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-bg relative flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="absolute top-4 right-4 z-20">
        <ThemeToggle variant="onHero" />
      </div>
      <div className="relative z-10 sm:mx-auto sm:w-full sm:max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <img
            src="/logo/utar-grader-logo.png"
            alt="UTAR Grader logo"
            className="w-14 h-14 object-contain mb-4 drop-shadow-md"
          />
          <h1 className="text-3xl font-extrabold tracking-[0.12em] text-white">UTAR GRADER</h1>
          <p className="mt-2 text-indigo-200/70 text-sm">AI-Powered Exam Grading</p>
        </div>

        {/* Card */}
        <div className="auth-card py-8 px-6 sm:px-10">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-slate-100 mb-6">
            Sign in to your account
          </h2>

          <form className="space-y-5" onSubmit={handleSubmit}>
            {error && (
              <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm animate-fade-in">
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
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="input-field"
                placeholder="••••••••"
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
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Signing in...
                </>
              ) : 'Sign in'}
            </button>

            <div className="text-right">
              <Link
                to="/forgot-password"
                className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300"
              >
                Forgot password?
              </Link>
            </div>
          </form>

          <div className="mt-6 text-center">
            <span className="text-sm text-gray-500 dark:text-slate-400">Don't have an account? </span>
            <Link
              to={nextAfterLogin ? `/register?next=${encodeURIComponent(nextAfterLogin)}` : '/register'}
              className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-500 dark:hover:text-indigo-300 transition-colors"
            >
              Register
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Login
