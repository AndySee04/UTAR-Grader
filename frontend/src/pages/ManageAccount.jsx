import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Cropper from 'react-easy-crop'
import 'react-easy-crop/react-easy-crop.css'
import { useAuth } from '../context/AuthContext'
import { accountAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

async function getCroppedImageBlob(imageSrc, croppedAreaPixels, fileType = 'image/jpeg') {
  const image = await new Promise((resolve, reject) => {
    const img = new Image()
    img.addEventListener('load', () => resolve(img))
    img.addEventListener('error', reject)
    img.src = imageSrc
  })

  const canvas = document.createElement('canvas')
  canvas.width = croppedAreaPixels.width
  canvas.height = croppedAreaPixels.height
  const ctx = canvas.getContext('2d')

  ctx.drawImage(
    image,
    croppedAreaPixels.x,
    croppedAreaPixels.y,
    croppedAreaPixels.width,
    croppedAreaPixels.height,
    0,
    0,
    croppedAreaPixels.width,
    croppedAreaPixels.height
  )

  return await new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), fileType, 0.95)
  })
}

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
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [deletingAccount, setDeletingAccount] = useState(false)
  const [cropModalOpen, setCropModalOpen] = useState(false)
  const [selectedImageSrc, setSelectedImageSrc] = useState(null)
  const [selectedImageType, setSelectedImageType] = useState('image/jpeg')
  const [crop, setCrop] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState(null)
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
    setDeletingAccount(true)
    try {
      await accountAPI.delete()
      logout()
      navigate('/login')
    } catch (err) {
      toast.error('Failed to delete account')
    } finally {
      setDeletingAccount(false)
      setDeleteModalOpen(false)
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

    const imageSrc = URL.createObjectURL(file)
    setSelectedImageSrc(imageSrc)
    setSelectedImageType(file.type || 'image/jpeg')
    setCrop({ x: 0, y: 0 })
    setZoom(1)
    setCroppedAreaPixels(null)
    setCropModalOpen(true)
    e.target.value = ''
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

  const handleCropCancel = () => {
    if (selectedImageSrc) URL.revokeObjectURL(selectedImageSrc)
    setSelectedImageSrc(null)
    setCropModalOpen(false)
  }

  const handleCropSave = async () => {
    if (!selectedImageSrc || !croppedAreaPixels) return
    setUploadingPhoto(true)
    try {
      const blob = await getCroppedImageBlob(selectedImageSrc, croppedAreaPixels, selectedImageType)
      if (!blob) throw new Error('Failed to prepare cropped image')
      const file = new File([blob], `profile-${Date.now()}.jpg`, { type: blob.type || 'image/jpeg' })
      await accountAPI.uploadProfilePicture(file)
      await checkAuth()
      toast.success('Profile picture updated')
      handleCropCancel()
      window.location.reload()
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Failed to upload profile picture')
    } finally {
      setUploadingPhoto(false)
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

  useEffect(() => {
    return () => {
      if (selectedImageSrc) URL.revokeObjectURL(selectedImageSrc)
    }
  }, [selectedImageSrc])

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Account Settings</h1>
        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Manage your profile and preferences</p>
      </div>

      {/* Profile Section */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="relative" ref={photoMenuRef}>
            <button
              type="button"
              onClick={() => setPhotoMenuOpen((open) => !open)}
              className="w-16 h-16 rounded-2xl overflow-hidden border border-gray-200 dark:border-slate-600 bg-gray-50 dark:bg-slate-800 flex items-center justify-center hover:ring-2 hover:ring-indigo-200 dark:hover:ring-indigo-700 transition-all"
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
                  className="w-10 h-10 text-gray-500 dark:text-slate-400"
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
              <div className="absolute left-1/2 top-full -translate-x-1/2 mt-2 z-20 w-52 rounded-xl border border-gray-200 dark:border-slate-600 bg-white dark:bg-slate-900 shadow-lg p-1.5">
                <button
                  type="button"
                  onClick={handlePickPhoto}
                  disabled={uploadingPhoto}
                  className="w-full text-left px-3 py-2 text-sm text-gray-700 dark:text-slate-200 rounded-lg hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-60"
                >
                  Upload Photo
                </button>
                <button
                  type="button"
                  onClick={handleRemovePhoto}
                  disabled={!user?.profile_picture_url}
                  className="w-full text-left px-3 py-2 text-sm text-red-600 dark:text-red-400 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/40 disabled:opacity-40 disabled:hover:bg-transparent"
                >
                  Remove Current Photo
                </button>
              </div>
            )}
          </div>
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-slate-100">Profile Information</h2>
            <p className="text-sm text-gray-500 dark:text-slate-400">Update your display name and profile picture</p>
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
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">Email</label>
            <input
              type="email"
              value={user?.email || ''}
              disabled
              className="input-field bg-gray-50 dark:bg-slate-800/80 text-gray-500 dark:text-slate-400 cursor-not-allowed"
            />
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">Email cannot be changed</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">Display Name</label>
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

      {cropModalOpen && selectedImageSrc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 shadow-2xl p-4 border border-gray-100 dark:border-slate-700">
            <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100">Crop Profile Photo</h3>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">Adjust zoom and position your photo.</p>

            <div className="relative mt-4 h-72 w-full rounded-xl overflow-hidden bg-gray-900">
              <Cropper
                image={selectedImageSrc}
                crop={crop}
                zoom={zoom}
                aspect={1}
                cropShape="round"
                showGrid={false}
                onCropChange={setCrop}
                onZoomChange={setZoom}
                onCropComplete={(_, pixels) => setCroppedAreaPixels(pixels)}
              />
            </div>

            <div className="mt-4">
              <label className="block text-xs font-medium text-gray-600 dark:text-slate-400 mb-2">Zoom</label>
              <input
                type="range"
                min={1}
                max={3}
                step={0.01}
                value={zoom}
                onChange={(e) => setZoom(Number(e.target.value))}
                className="w-full accent-indigo-600"
              />
            </div>

            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={handleCropCancel}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-200 bg-gray-100 dark:bg-slate-800 rounded-lg hover:bg-gray-200 dark:hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleCropSave}
                disabled={uploadingPhoto}
                className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 disabled:opacity-60"
              >
                {uploadingPhoto ? 'Saving...' : 'Save Photo'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Password Section */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-slate-800 flex items-center justify-center">
            <svg className="w-6 h-6 text-gray-500 dark:text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
          </div>
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-slate-100">Change Password</h2>
            <p className="text-sm text-gray-500 dark:text-slate-400">Update your security credentials</p>
          </div>
        </div>
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">Current Password</label>
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
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              className="input-field"
              placeholder="••••••••"
            />
            <p className="text-xs text-gray-400 dark:text-slate-500 mt-1">Minimum 6 characters</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">Confirm New Password</label>
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
      <div className="card p-6 border-2 border-red-100 dark:border-red-900/50">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-12 h-12 rounded-2xl bg-red-50 dark:bg-red-950/40 flex items-center justify-center">
            <svg className="w-6 h-6 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
            </svg>
          </div>
          <div>
            <h2 className="font-semibold text-red-600 dark:text-red-400">Danger Zone</h2>
            <p className="text-sm text-gray-500 dark:text-slate-400">Irreversible account actions</p>
          </div>
        </div>
        <p className="text-sm text-gray-600 dark:text-slate-400 mb-4">
          Once you delete your account, there is no going back. All your exams, grades, and data will be permanently deleted.
        </p>
        <button
          onClick={() => setDeleteModalOpen(true)}
          className="btn-danger flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
          Delete Account
        </button>
      </div>

      {deleteModalOpen && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/55 backdrop-blur-[1px] p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-gray-100 dark:border-slate-700">
            <div className="p-5">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Delete Account?</h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-slate-400">
                Are you sure you want to delete your account? This action cannot be undone.
                All your exams, grades, and uploaded files will be permanently deleted.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/80 rounded-b-2xl">
              <button
                onClick={() => setDeleteModalOpen(false)}
                disabled={deletingAccount}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-200 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-white dark:hover:bg-slate-700 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteAccount}
                disabled={deletingAccount}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deletingAccount ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ManageAccount
