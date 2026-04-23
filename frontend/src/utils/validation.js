export function isValidEmail(email) {
  const value = String(email || '').trim()
  if (!value) return false
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
}
