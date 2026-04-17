import React, { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'

const CAPTURE_JPEG_QUALITY = 0.9
const MAX_CAPTURE_SIDE = 1600

function CaptureSession() {
  const { sessionId } = useParams()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const [session, setSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [capturing, setCapturing] = useState(false)
  const [pages, setPages] = useState([])
  const [replaceIndex, setReplaceIndex] = useState(null)
  const [activePageId, setActivePageId] = useState(null)
  const [finalizing, setFinalizing] = useState(false)
  const [completed, setCompleted] = useState(false)
  const [captureStatus, setCaptureStatus] = useState('')
  const [showStudentContinuePrompt, setShowStudentContinuePrompt] = useState(false)
  const [continuing, setContinuing] = useState(false)
  const [exiting, setExiting] = useState(false)
  const [focusMarker, setFocusMarker] = useState(null)

  const pageCountLabel = useMemo(() => `${pages.length} page${pages.length === 1 ? '' : 's'}`, [pages.length])

  useEffect(() => {
    let mounted = true
    if (!sessionId || !token) {
      setError('Invalid capture link. Missing session token.')
      setLoading(false)
      return
    }
    const loadSession = async () => {
      try {
        const sessionRes = await fetch(`/api/capture-sessions/${sessionId}?token=${encodeURIComponent(token)}`)
        if (!sessionRes.ok) {
          let detail = 'Failed to load capture session'
          try {
            const data = await sessionRes.json()
            detail = data?.detail || detail
          } catch {
            // Keep fallback detail.
          }
          throw new Error(detail)
        }
        const sessionData = await sessionRes.json()
        if (!mounted) return
        setSession(sessionData)
        if (sessionData?.status === 'completed') setCompleted(true)

        const pagesRes = await fetch(`/api/capture-sessions/${sessionId}/pages?token=${encodeURIComponent(token)}`)
        if (!pagesRes.ok) {
          setPages([])
          return
        }
        const pagesData = await pagesRes.json()
        if (!mounted) return
        const serverPages = Array.isArray(pagesData?.pages) ? pagesData.pages : []
        setPages(serverPages.map((p) => ({
          id: p.id,
          previewUrl: p.preview_url,
          width: p.width,
          height: p.height,
          processedSuccess: p.processed_success !== false,
          processingNote: p.processing_note || ''
        })))
      } catch (err) {
        if (!mounted) return
        setError(err?.message || 'Failed to load capture session')
      } finally {
        if (mounted) setLoading(false)
      }
    }
    loadSession()
    return () => { mounted = false }
  }, [sessionId, token])

  useEffect(() => {
    let mounted = true
    if (loading || completed) return undefined
    const start = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1920 },
            height: { ideal: 1080 }
          },
          audio: false
        })
        if (!mounted) return
        streamRef.current = stream
        const video = videoRef.current
        if (video) {
          video.srcObject = stream
          try {
            await video.play()
          } catch {
            // Some mobile browsers block autoplay promises; tap still starts capture.
          }
        }
      } catch (e) {
        if (!mounted) return
        setError(e?.message || 'Camera access denied.')
      }
    }

    start()
    return () => {
      mounted = false
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
        streamRef.current = null
      }
    }
  }, [loading, completed])

  const handleTapToFocus = async (event) => {
    const video = videoRef.current
    const stream = streamRef.current
    if (!video || !stream) return
    const track = stream.getVideoTracks()?.[0]
    if (!track) return

    const rect = video.getBoundingClientRect()
    if (!rect.width || !rect.height) return
    const clientX = event.clientX ?? (event.touches?.[0]?.clientX)
    const clientY = event.clientY ?? (event.touches?.[0]?.clientY)
    if (clientX == null || clientY == null) return

    const nx = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width))
    const ny = Math.max(0, Math.min(1, (clientY - rect.top) / rect.height))
    setFocusMarker({
      leftPct: nx * 100,
      topPct: ny * 100,
    })
    setTimeout(() => setFocusMarker(null), 900)

    const capabilities = track.getCapabilities?.() || {}
    const advanced = []
    if (capabilities.focusMode) {
      if (capabilities.focusMode.includes('single-shot')) {
        advanced.push({ focusMode: 'single-shot' })
      } else if (capabilities.focusMode.includes('continuous')) {
        advanced.push({ focusMode: 'continuous' })
      }
    }
    if (capabilities.pointsOfInterest) {
      advanced.push({ pointsOfInterest: [{ x: nx, y: ny }] })
    }
    if (!advanced.length) return

    try {
      await track.applyConstraints({ advanced })
      setCaptureStatus('Focus adjusted')
    } catch {
      // Device/browser may not support focus constraints.
    }
  }

  const capturePage = async () => {
    if (capturing) return
    const video = videoRef.current
    if (!video) {
      setError('Camera is not initialized yet.')
      return
    }
    if ((video.videoWidth || 0) < 2 || (video.videoHeight || 0) < 2) {
      setError('Camera is still starting. Please try again in a moment.')
      return
    }
    setCapturing(true)
    setCaptureStatus('Capturing photo...')
    setError('')
    try {
      const canvas = document.createElement('canvas')
      const srcW = video.videoWidth || 1280
      const srcH = video.videoHeight || 720
      const maxSide = Math.max(srcW, srcH)
      const scale = maxSide > MAX_CAPTURE_SIDE ? MAX_CAPTURE_SIDE / maxSide : 1
      canvas.width = Math.max(1, Math.round(srcW * scale))
      canvas.height = Math.max(1, Math.round(srcH * scale))
      const ctx = canvas.getContext('2d')
      if (!ctx) {
        throw new Error('Could not create canvas context')
      }
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob((result) => {
          if (result) resolve(result)
          else reject(new Error('Failed to capture image frame'))
        }, 'image/jpeg', CAPTURE_JPEG_QUALITY)
      })
      if (!blob || blob.size <= 0) {
        throw new Error('Captured image blob is empty')
      }
      setCaptureStatus('Uploading page...')
      const formData = new FormData()
      formData.append('token', token)
      formData.append('file', blob, `capture_${Date.now()}.jpg`)
      const uploadResp = await fetch(`/api/capture-sessions/${sessionId}/pages`, {
        method: 'POST',
        body: formData
      })
      if (!uploadResp.ok) {
        let detail = 'Failed to upload captured page'
        try {
          const data = await uploadResp.json()
          detail = data?.detail || detail
        } catch {
          // Keep fallback detail.
        }
        throw new Error(detail)
      }
      const uploaded = await uploadResp.json()
      const next = {
        id: uploaded?.id || crypto.randomUUID(),
        previewUrl: uploaded?.preview_url || '',
        width: uploaded?.width,
        height: uploaded?.height,
        processedSuccess: uploaded?.processed_success !== false,
        processingNote: uploaded?.processing_note || ''
      }
      if (replaceIndex != null && pages[replaceIndex]?.id) {
        await fetch(
          `/api/capture-sessions/${sessionId}/pages/${pages[replaceIndex].id}?token=${encodeURIComponent(token)}`,
          { method: 'DELETE' }
        )
      }
      setPages((prev) => {
        if (replaceIndex == null) return [...prev, next]
        return prev.map((p, idx) => (idx === replaceIndex ? next : p))
      })
      setReplaceIndex(null)
      setCaptureStatus('Page captured successfully.')
    } catch (e) {
      setCaptureStatus('')
      setError(e?.response?.data?.detail || e?.message || 'Failed to capture page')
    } finally {
      setCapturing(false)
    }
  }

  const movePage = (index, direction) => {
    setPages((prev) => {
      const target = index + direction
      if (target < 0 || target >= prev.length) return prev
      const copy = [...prev]
      const [item] = copy.splice(index, 1)
      copy.splice(target, 0, item)
      return copy
    })
  }

  const deletePageById = async (pageId, opts = {}) => {
    const { updateState = true } = opts
    const deleteResp = await fetch(
      `/api/capture-sessions/${sessionId}/pages/${pageId}?token=${encodeURIComponent(token)}`,
      { method: 'DELETE' }
    )
    if (!deleteResp.ok) {
      throw new Error('Failed to delete page')
    }
    if (!updateState) return

    let deletedIndex = -1
    setPages((prev) => {
      deletedIndex = prev.findIndex((p) => p.id === pageId)
      return prev.filter((p) => p.id !== pageId)
    })
    setActivePageId((prev) => (prev === pageId ? null : prev))
    if (replaceIndex != null && deletedIndex >= 0) {
      if (deletedIndex === replaceIndex) setReplaceIndex(null)
      else if (deletedIndex < replaceIndex) setReplaceIndex(replaceIndex - 1)
    }
  }

  const handleFinalizeCapture = async () => {
    if (!sessionId || !token || pages.length === 0 || finalizing) return
    setFinalizing(true)
    setCaptureStatus('Processing photos on laptop/server...')
    setError('')
    try {
      setCaptureStatus('Generating final PDF on server...')
      const finalizeResp = await fetch(`/api/capture-sessions/${sessionId}/finalize`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          page_ids: pages.map((p) => p.id)
        })
      })
      if (!finalizeResp.ok) {
        let detail = 'Failed to finalize capture'
        try {
          const data = await finalizeResp.json()
          detail = data?.detail || detail
        } catch {
          // Keep fallback detail.
        }
        throw new Error(detail)
      }
      setCompleted(true)
      setSession((prev) => ({ ...(prev || {}), status: 'completed' }))
      setCaptureStatus('Done. PDF uploaded successfully.')
      if ((session?.doc_type || '') === 'student_answer') {
        setShowStudentContinuePrompt(true)
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop())
        streamRef.current = null
      }
    } catch (e) {
      setCaptureStatus('')
      setError(e?.response?.data?.detail || e?.message || 'Failed to finalize capture')
    } finally {
      setFinalizing(false)
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-slate-950 p-4 flex items-center justify-center text-gray-600 dark:text-slate-300">
        Loading capture session...
      </div>
    )
  }

  const activePage = pages.find((p) => p.id === activePageId) || null
  const activePageIndex = activePage ? pages.findIndex((p) => p.id === activePage.id) : -1

  const handleContinueStudentCapture = async () => {
    if (!sessionId || !token || continuing) return
    setContinuing(true)
    setError('')
    try {
      const resp = await fetch(`/api/capture-sessions/${sessionId}/continue`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      })
      if (!resp.ok) {
        let detail = 'Failed to create next capture session'
        try {
          const data = await resp.json()
          detail = data?.detail || detail
        } catch {
          // keep default
        }
        throw new Error(detail)
      }
      const data = await resp.json()
      const nextUrl = data?.mobile_url
      if (!nextUrl) throw new Error('Next capture URL missing')
      window.location.href = nextUrl
    } catch (e) {
      setError(e?.message || 'Failed to continue capture')
      setContinuing(false)
    }
  }

  const handleExitStudentCapture = async () => {
    if (!sessionId || !token || exiting) return
    setExiting(true)
    setError('')
    try {
      const resp = await fetch(`/api/capture-sessions/${sessionId}/exit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      })
      if (!resp.ok) {
        let detail = 'Failed to close capture session'
        try {
          const data = await resp.json()
          detail = data?.detail || detail
        } catch {
          // keep default
        }
        throw new Error(detail)
      }
      setShowStudentContinuePrompt(false)
    } catch (e) {
      setError(e?.message || 'Failed to close capture session')
    } finally {
      setExiting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-slate-950 p-4 space-y-4">
      <div className="max-w-3xl mx-auto bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-4 space-y-4">
        <div>
          <h1 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Phone Document Capture</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400">
            {session?.doc_type === 'question_paper' ? 'Question Paper' : 'Student Answer'} • {pageCountLabel}
          </p>
        </div>

        {error && (
          <div className="text-sm rounded-lg border border-red-200 bg-red-50 text-red-700 px-3 py-2">{error}</div>
        )}

        {completed ? (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 text-emerald-700 px-3 py-3 text-sm">
            PDF uploaded successfully. <br />
            You can return to your desktop.
          </div>
        ) : (
          <>
            <div
              className="rounded-lg overflow-hidden bg-black relative"
              onPointerDown={handleTapToFocus}
            >
              <video ref={videoRef} className="w-full h-auto max-h-[55vh] object-contain" playsInline muted autoPlay />
              {focusMarker && (
                <div
                  className="absolute w-10 h-10 border-2 border-emerald-400 rounded-full pointer-events-none"
                  style={{
                    left: `${focusMarker.leftPct}%`,
                    top: `${focusMarker.topPct}%`,
                    transform: 'translate(-50%, -50%)',
                  }}
                />
              )}
            </div>
            <div className="pt-2">
              {replaceIndex != null && (
                <div className="mb-2 flex items-center justify-between rounded-md border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-700">
                  <span>Retake mode for page #{replaceIndex + 1}</span>
                  <button
                    type="button"
                    className="underline"
                    onClick={() => setReplaceIndex(null)}
                  >
                    Cancel retake
                  </button>
                </div>
              )}
              <div className="flex items-center justify-center">
                <button
                  type="button"
                  onClick={capturePage}
                  disabled={capturing}
                  className="w-16 h-16 rounded-full border-4 border-indigo-500 bg-white text-indigo-700 flex items-center justify-center shadow-md disabled:opacity-60"
                  title={replaceIndex == null ? 'Capture photo' : `Retake page ${replaceIndex + 1}`}
                >
                  {capturing ? (
                    <svg className="animate-spin h-6 w-6" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                    </svg>
                  ) : (
                    <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7h4l2-2h6l2 2h4v12H3V7z" />
                      <circle cx="12" cy="13" r="4" strokeWidth={2} />
                    </svg>
                  )}
                </button>
              </div>
              <p className="mt-1 text-center text-xs text-gray-500 dark:text-slate-400">
                {capturing ? 'Capturing...' : replaceIndex == null ? 'Camera capture' : `Retake page #${replaceIndex + 1}`}
              </p>
            </div>
            {captureStatus && (
              <div className="text-xs text-indigo-700 bg-indigo-50 border border-indigo-200 rounded-md px-2 py-1">
                {captureStatus}
              </div>
            )}
          </>
        )}
      </div>

      {!completed && pages.length > 0 && (
        <div className="max-w-3xl mx-auto bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-4">
          <h2 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-3">Captured Pages</h2>
          <div className="flex gap-2 overflow-x-auto pb-2">
            {pages.map((p, idx) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setActivePageId(p.id)}
                className={`min-w-[76px] w-[76px] rounded-lg p-1 border-2 shrink-0 ${
                  p.processedSuccess ? 'border-emerald-400' : 'border-red-500'
                }`}
                title={p.processingNote || (p.processedSuccess ? 'Processed successfully' : 'Processing fallback')}
              >
                <img src={p.previewUrl} alt={`Captured page ${idx + 1}`} className="w-full h-[58px] object-cover rounded" />
                <div className="mt-1 text-[11px] text-center text-gray-700 dark:text-slate-300">#{idx + 1}</div>
              </button>
            ))}
          </div>
          <div className="mt-4">
            <button
              type="button"
              onClick={handleFinalizeCapture}
              disabled={pages.length === 0 || finalizing}
              className="btn-secondary w-full"
            >
              {finalizing ? 'Confirming...' : 'Confirm & Upload PDF'}
            </button>
          </div>
        </div>
      )}

      {!completed && activePage && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100">
                Page {activePageIndex + 1}
              </h3>
              <button
                type="button"
                onClick={() => setActivePageId(null)}
                className="text-gray-500 hover:text-gray-700 dark:hover:text-slate-200"
              >
                Close
              </button>
            </div>
            <img
              src={activePage.previewUrl}
              alt={`Captured page ${activePageIndex + 1}`}
              className={`w-full max-h-[65vh] object-contain rounded border-2 ${
                activePage.processedSuccess ? 'border-emerald-400' : 'border-red-500'
              }`}
            />
            {!activePage.processedSuccess && (
              <p className="text-xs text-red-600">
                Processing fallback detected for this page. <br />
                You can retake or delete this page.
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary flex-1"
                onClick={() => {
                  setReplaceIndex(activePageIndex)
                  setActivePageId(null)
                }}
              >
                Retake
              </button>
              <button
                type="button"
                className="text-xs px-3 py-2 rounded border border-red-300 text-red-600 hover:bg-red-50"
                onClick={async () => {
                  try {
                    await deletePageById(activePage.id)
                  } catch (e) {
                    setError(e?.message || 'Failed to delete page')
                  }
                }}
              >
                Delete
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => movePage(activePageIndex, -1)}
                disabled={activePageIndex <= 0}
              >
                ←
              </button>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => movePage(activePageIndex, 1)}
                disabled={activePageIndex < 0 || activePageIndex >= pages.length - 1}
              >
                →
              </button>
            </div>
          </div>
        </div>
      )}

      {completed && showStudentContinuePrompt && (
        <div className="fixed inset-0 z-50 bg-black/45 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-sm bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-700 p-4 space-y-3">
            <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100">PDF uploaded successfully</h3>
            <p className="text-sm text-gray-600 dark:text-slate-300">
              Do you want to capture another student answer now?
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleContinueStudentCapture}
                disabled={continuing || exiting}
                className="btn-primary flex-1"
              >
                {continuing ? 'Opening...' : 'Capture Another'}
              </button>
              <button
                type="button"
                onClick={handleExitStudentCapture}
                disabled={continuing || exiting}
                className="btn-secondary"
              >
                {exiting ? 'Exiting...' : 'Exit'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default CaptureSession
