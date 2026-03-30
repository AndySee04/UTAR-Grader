import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useEffect, useRef, useState } from 'react'

const NAV_ITEMS = [
  {
    to: '/exams',
    label: 'My Exams',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
      </svg>
    )
  },
  {
    to: '/grade',
    label: 'Grade Paper',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    )
  },
  {
    to: '/account',
    label: 'Account',
    icon: (
      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    )
  }
]

function Navbar() {
  const { user, logout } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [accountMenuOpen, setAccountMenuOpen] = useState(false)
  const navigate = useNavigate()
  const accountMenuRef = useRef(null)

  const linkClass = ({ isActive }) =>
    `flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 ${
      isActive
        ? 'bg-indigo-600 text-white shadow-md shadow-indigo-500/25'
        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
    }`

  useEffect(() => {
    const onDocClick = (event) => {
      if (!accountMenuRef.current) return
      if (!accountMenuRef.current.contains(event.target)) {
        setAccountMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  return (
    <nav className="bg-white/80 backdrop-blur-xl border-b border-gray-100 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex justify-between h-16">
          {/* Logo + Nav */}
          <div className="flex items-center">
            <button
              type="button"
              onClick={() => navigate('/exams')}
              className="flex items-center gap-2 mr-8 select-none"
              aria-label="Go to My Exams"
            >
              <img
                src="/logo/utar-grader-logo.png"
                alt="UTAR Grader logo"
                className="w-8 h-8 object-contain"
                draggable="false"
              />
              <span className="text-lg font-extrabold tracking-[0.12em] text-black hidden sm:block select-none">
                UTAR GRADER
              </span>
            </button>

            {/* Desktop nav */}
            <div className="hidden md:flex items-center gap-1">
              {NAV_ITEMS.map(item => (
                <NavLink key={item.to} to={item.to} className={linkClass}>
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-3">
            <div className="relative hidden sm:block" ref={accountMenuRef}>
              <button
                type="button"
                onClick={() => setAccountMenuOpen((open) => !open)}
                className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-50 text-sm hover:bg-gray-100 transition-colors"
              >
                <div className="w-7 h-7 rounded-full bg-indigo-100 flex items-center justify-center overflow-hidden">
                  {user?.profile_picture_url ? (
                    <img
                      src={user.profile_picture_url}
                      alt="Profile"
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <svg className="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M20 21a8 8 0 10-16 0" />
                      <circle cx="12" cy="8" r="4" strokeWidth={1.8} />
                    </svg>
                  )}
                </div>
                <span className="text-gray-600 font-medium">{user?.name || user?.email}</span>
              </button>
              {accountMenuOpen && (
                <div className="absolute right-0 mt-2 w-44 rounded-xl border border-gray-200 bg-white shadow-lg p-1.5 z-30">
                  <button
                    type="button"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      navigate('/account')
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2"
                  >
                    <svg className="w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M10.325 4.317a1 1 0 011.35-.936l.145.056 1.5.6a1 1 0 01.598.72l.026.147.11 1.02a1 1 0 00.6.81l.157.06 1.02.34a1 1 0 01.654.605l.047.147.3 1.5a1 1 0 01-.356.977l-.123.09-.823.55a1 1 0 00-.404.616l-.026.162v1.08a1 1 0 00.312.724l.118.094.823.55a1 1 0 01.434 1.01l-.03.147-.3 1.5a1 1 0 01-.53.7l-.17.075-1.02.34a1 1 0 00-.688.68l-.04.19-.11 1.02a1 1 0 01-.492.75l-.132.07-1.5.6a1 1 0 01-1.03-.162l-.114-.106-.72-.72a1 1 0 00-.606-.287L11 20h-1.08a1 1 0 00-.648.238l-.12.108-.72.72a1 1 0 01-.985.25l-.145-.056-1.5-.6a1 1 0 01-.598-.72l-.026-.147-.11-1.02a1 1 0 00-.6-.81l-.157-.06-1.02-.34a1 1 0 01-.654-.605l-.047-.147-.3-1.5a1 1 0 01.356-.977l.123-.09.823-.55a1 1 0 00.404-.616l.026-.162v-1.08a1 1 0 00-.312-.724l-.118-.094-.823-.55a1 1 0 01-.434-1.01l.03-.147.3-1.5a1 1 0 01.53-.7l.17-.075 1.02-.34a1 1 0 00.688-.68l.04-.19.11-1.02a1 1 0 01.492-.75l.132-.07 1.5-.6a1 1 0 011.03.162l.114.106.72.72a1 1 0 00.606.287L9.92 4h1.08a1 1 0 00.648-.238l.12-.108.72-.72z" />
                      <circle cx="10.5" cy="12" r="2.5" strokeWidth={1.6} />
                    </svg>
                    Settings
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setAccountMenuOpen(false)
                      logout()
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-red-600 rounded-lg hover:bg-red-50 flex items-center gap-2"
                  >
                    <svg className="w-4 h-4 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M17 16l4-4m0 0l-4-4m4 4H9" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13 7V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2h5a2 2 0 002-2v-1" />
                    </svg>
                    Logout
                  </button>
                </div>
              )}
            </div>
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileOpen(!mobileOpen)}
              className="md:hidden p-2 text-gray-500 hover:bg-gray-100 rounded-lg"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                {mobileOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>

        {/* Mobile nav */}
        {mobileOpen && (
          <div className="md:hidden pb-4 border-t border-gray-100 pt-2 animate-fade-in">
            <div className="flex flex-col gap-1">
              {NAV_ITEMS.map(item => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={() => setMobileOpen(false)}
                  className={linkClass}
                >
                  {item.icon}
                  <span>{item.label}</span>
                </NavLink>
              ))}
              <button
                type="button"
                onClick={() => {
                  setMobileOpen(false)
                  navigate('/account')
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-all duration-200"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                </svg>
                <span>Settings</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setMobileOpen(false)
                  logout()
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium text-red-600 hover:bg-red-50 transition-all duration-200"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                </svg>
                <span>Logout</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </nav>
  )
}

export default Navbar
