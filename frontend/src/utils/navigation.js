/**
 * Safe in-app redirect target after login (relative path only).
 */
export function sanitizeNext(raw) {
  if (!raw || typeof raw !== 'string') return null
  const t = raw.trim()
  if (!t.startsWith('/') || t.startsWith('//')) return null
  return t
}
