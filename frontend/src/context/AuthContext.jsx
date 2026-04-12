/**
 * Barrel re-exports so existing imports from `context/AuthContext` keep working.
 * Provider and hook live in separate modules for React Fast Refresh compatibility.
 */
export { AuthProvider } from './AuthProvider'
export { useAuth } from './useAuth'
