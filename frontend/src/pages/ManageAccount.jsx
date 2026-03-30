import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { accountAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

function ManageAccount() {
  const { user, logout, checkAuth } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()

  const [name, setName] = useState(user?.name || '')
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [uploadingPhoto, setUploadingPhoto] = useState(false)
  const [photoMenuOpen, setPhotoMenuOpen] = useState(false)
  const photoInputRef = useRef(null)
  const photoMenuRef = useRef(null)
  const hasNameChanged = name !== (user?.name || '')

  const handleUpdateProfile = async (e) => {
    e.preventDefault()
    setLoading(true)

    try {
      await accountAPI.update({ name })
      await checkAuth()
      toast.success('Profile updated successfully')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update profile')
    } finally {
      setLoading(false)
    }
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()

    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match')
      return
    }

    if (newPassword.length < 6) {
      toast.error('Password must be at least 6 characters')
      return
    }

    setLoading(true)

    try {
      await accountAPI.changePassword({
        current_password: currentPassword,
        new_password: newPassword
      })
      toast.success('Password changed successfully')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to change password')
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteAccount = async () => {
    if (!confirm('Are you sure you want to delete your account? This action cannot be undone. All your exams and data will be permanently deleted.')) {
      return
    }

    try {
      await accountAPI.delete()
      logout()
      navigate('/login')
    } catch (err) {
      toast.error('Failed to delete account')
    }
  }

  const handlePickPhoto = () => {
    setPhotoMenuOpen(false)
    photoInputRef.current?.click()
  }

  const handlePhotoChange = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.type.startsWith('image/')) {
      toast.error('Please select an image file')
      return
    }

    setUploadingPhoto(true)
    try {
      await accountAPI.uploadProfilePicture(file)
      await checkAuth()
      toast.success('Profile picture updated')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to upload profile picture')
    } finally {
      setUploadingPhoto(false)
      e.target.value = ''
    }
  }

  const handleRemovePhoto = async () => {
    setPhotoMenuOpen(false)
    try {
      await accountAPI.removeProfilePicture()
      await checkAuth()
      toast.success('Profile picture removed')
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to remove profile picture')
    }
  }

  useEffect(() => {
    const onDocClick = (event) => {
      if (!photoMenuRef.current) return
      if (!photoMenuRef.current.contains(event.target)) {
        setPhotoMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Account Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your profile and preferences</p>
      </div>

      {/* Profile Section */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="relative" ref={photoMenuRef}>
            <button
              type="button"
              onClick={() => setPhotoMenuOpen((open) => !open)}
              className="w-16 h-16 rounded-2xl overflow-hidden border border-gray-200 bg-gray-50 flex items-center justify-center hover:ring-2 hover:ring-indigo-200 transition-all"
              title="Profile picture options"
            >
              {user?.profile_picture_url ? (
                <img
                  src={user.profile_picture_url}
                  alt="Profile"
                  className="w-full h-full object-cover"
                />
              ) : (
                <svg
                  className="w-10 h-10 text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1.8}
                    d="M20 21a8 8 0 10-16 0"
                  />
                  <circle cx="12" cy="8" r="4" strokeWidth={1.8} />
                </svg>
              )}
            </button>
            {photoMenuOpen && (
              <div className="absolute left-1/2 top-full -translate-x-1/2 mt-2 z-20 w-52 rounded-xl border border-gray-200 bg-white shadow-lg p-1.5">
                <button
                  type="button"
                  onClick={handlePickPhoto}
                  disabled={uploadingPhoto}
                  className="w-full text-left px-3 py-2 text-sm text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-60"
                >
                  Upload Photo
                </button>
                <button
                  type="button"
                  onClick={handleRemovePhoto}
                  disabled={!user?.profile_picture_url}
                  className="w-full text-left px-3 py-2 text-sm text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-40 disabled:hover:bg-transparent"
                >
                  Remove Current Photo
                </button>
              </div>
            )}
          </div>
          <div>
            <h2 className="font-semibold text-gray-900">Profile Information</h2>
            <p className="text-sm text-gray-500">Update your display name and profile picture</p>
          </div>
        </div>
        <input
          ref={photoInputRef}
          type="file"
          accept="image/*"
          onChange={handlePhotoChange}
          className="hidden"
        />
        <form onSubmit={handleUpdateProfile} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Email</label>
            <input
              type="email"
              value={user?.email || ''}
              disabled
              className="input-field bg-gray-50 text-gray-500 cursor-not-allowed"
            />
            <p className="text-xs text-gray-400 mt-1">Email cannot be changed</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Display Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input-field"
              placeholder="Your name"
            />
          </div>

          <button
            type="submit"
            disabled={loading || !hasNameChanged}
            className="btn-primary flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Saving...
              </>
            ) : 'Save Changes'}
          </button>
        </form>
      </div>

      {/* Password Section */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gray-100 flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <h2 className="font-semibold text-gray-900">Change Password</h2>
            <p className="text-sm text-gray-500">Update your security credentials</p>
          </div>
        </div>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Current Password</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              className="input-field"
              placeholder="••••••••"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="input-field"
              placeholder="••••••••"
            />
            <p className="text-xs text-gray-400 mt-1">Minimum 6 characters</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              className="input-field"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary flex items-center gap-2"
          >
            {loading ? 'Changing...' : 'Change Password'}
          </button>
        </form>
      </div>

      {/* Danger Zone */}
      <div className="card p-6 border-2 border-red-100">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-red-50 flex items-center justify-center">
            <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div>
            <h2 className="font-semibold text-red-600">Danger Zone</h2>
            <p className="text-sm text-gray-500">Irreversible account actions</p>
          </div>
        </div>
        <p className="text-sm text-gray-600 mb-4">
          Once you delete your account, there is no going back. All your exams, grades, and data will be permanently deleted.
        </p>
        <button
          onClick={handleDeleteAccount}
          className="btn-danger flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Delete Account
        </button>
      </div>
    </div>
  )
}

export default ManageAccount
