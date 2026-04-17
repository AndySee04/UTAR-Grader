import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { examsAPI, documentsAPI, processingAPI, markingGuideAPI, gradingAPI, captureAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

const STEPS = [
  { label: 'Upload', icon: 'upload' },
  { label: 'Process', icon: 'settings' },
  { label: 'Marking Guide', icon: 'clipboard-list' },
  { label: 'Grade', icon: 'check' }
]

function StepIcon({ name, className = 'w-5 h-5' }) {
  const baseProps = {
    className,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': true
  }

  if (name === 'upload') {
    return (
      <svg {...baseProps}>
        <path d="M12 3v12" />
        <path d="M8 7l4 -4l4 4" />
        <path d="M4 15v2a4 4 0 0 0 4 4h8a4 4 0 0 0 4 -4v-2" />
      </svg>
    )
  }

  if (name === 'settings') {
    return (
      <svg {...baseProps}>
        <path d="M12 9a3 3 0 1 0 0 6a3 3 0 0 0 0 -6" />
        <path d="M12 3l0 2" />
        <path d="M12 19l0 2" />
        <path d="M3 12l2 0" />
        <path d="M19 12l2 0" />
        <path d="M5.6 5.6l1.4 1.4" />
        <path d="M17 17l1.4 1.4" />
        <path d="M17 7l1.4 -1.4" />
        <path d="M5.6 18.4l1.4 -1.4" />
      </svg>
    )
  }

  if (name === 'clipboard-list') {
    return (
      <svg {...baseProps}>
        <path d="M9 5h6a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-6a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2z" />
        <path d="M9 5a2 2 0 0 1 2 -2h2a2 2 0 0 1 2 2" />
        <path d="M10 12h4" />
        <path d="M10 16h4" />
      </svg>
    )
  }

  return (
    <svg {...baseProps}>
      <path d="M5 12l5 5l10 -10" />
    </svg>
  )
}

function GradePaper() {
  const [step, setStep] = useState(0)
  const [examId, setExamId] = useState(null)
  const [examName, setExamName] = useState('')
  const [questionPaper, setQuestionPaper] = useState(null)
  const [answerScheme, setAnswerScheme] = useState(null)
  const [studentAnswers, setStudentAnswers] = useState([])
  const [uploadedDocs, setUploadedDocs] = useState({ question: null, scheme: null, students: [] })
  const [markingGuide, setMarkingGuide] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [processing, setProcessing] = useState(false)
  const [processStatus, setProcessStatus] = useState('')
  const [examStatus, setExamStatus] = useState(null) 
  const [dragActive, setDragActive] = useState(null)
  
  // OCR Region View State
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [selectedDocType, setSelectedDocType] = useState(null) // 'question' | 'student_answer'
  const [regions, setRegions] = useState([])
  const [questionTemplateRegions, setQuestionTemplateRegions] = useState([])
  const [loadingRegions, setLoadingRegions] = useState(false)
  const [runningOcrFor, setRunningOcrFor] = useState(null)
  const [showRegionModal, setShowRegionModal] = useState(false)

  // Manual crop state
  const [pages, setPages] = useState([])
  const [activePage, setActivePage] = useState(null)
  const [isCropping, setIsCropping] = useState(false)
  const [cropStart, setCropStart] = useState(null)
  const [cropEnd, setCropEnd] = useState(null)
  const pageImgRefs = useRef({})
  const cropImageRef = useRef(null)
  const cropStartRef = useRef(null)
  const cropEndRef = useRef(null)
  const [pageImageUrls, setPageImageUrls] = useState({})
  const [pageDimensions, setPageDimensions] = useState({})
  const [loadingPageImages, setLoadingPageImages] = useState(false)
  const [processingNewCrop, setProcessingNewCrop] = useState(false)
  const editFocusRef = useRef({ id: null, value: null })
  const addStudentInputRef = useRef(null)

  // Region count per document (synced with backend); cropped = count > 0
  const [regionCountByDocId, setRegionCountByDocId] = useState({})
  const [answerGuideDrafts, setAnswerGuideDrafts] = useState({})
  const [savingAnswerGuideId, setSavingAnswerGuideId] = useState(null)
  const [autoCleanupEnabled, setAutoCleanupEnabled] = useState(true)
  const [regionCleanupMeta, setRegionCleanupMeta] = useState({})
  const [gradingProvider, setGradingProvider] = useState('ollama')
  const [gradingModel, setGradingModel] = useState('')
  const [captureDialog, setCaptureDialog] = useState({ open: false, loading: false, docType: null, url: '', sessionId: '', expiresAt: null })

  const croppedDocs = useMemo(
    () => new Set(Object.entries(regionCountByDocId).filter(([, c]) => c > 0).map(([id]) => id)),
    [regionCountByDocId]
  )

  const croppedStudentCount = useMemo(
    () =>
      (uploadedDocs.students || []).filter(
        (doc) => (regionCountByDocId[doc.id] ?? 0) > 0
      ).length,
    [uploadedDocs.students, regionCountByDocId]
  )

  const allStudentsCropped =
    uploadedDocs.students &&
    uploadedDocs.students.length > 0 &&
    uploadedDocs.students.every((doc) => (regionCountByDocId[doc.id] ?? 0) > 0)

  const studentDocs = uploadedDocs.students || []

  // Helpers for question-number colouring and marks extraction (question paper only)
  const QUESTION_COLOR_PALETTE = [
    {
      border: 'border-emerald-500/90',
      fillBorder: 'border-emerald-500/90',
      fillBg: 'bg-emerald-400/25',
      badge: 'bg-emerald-100 dark:bg-emerald-950/50 text-emerald-800 dark:text-emerald-300'
    },
    {
      border: 'border-indigo-500/90',
      fillBorder: 'border-indigo-500/90',
      fillBg: 'bg-indigo-400/20',
      badge: 'bg-indigo-100 dark:bg-indigo-950/50 text-indigo-800 dark:text-indigo-300'
    },
    {
      border: 'border-amber-500/90',
      fillBorder: 'border-amber-500/90',
      fillBg: 'bg-amber-400/25',
      badge: 'bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300'
    },
    {
      border: 'border-rose-500/90',
      fillBorder: 'border-rose-500/90',
      fillBg: 'bg-rose-400/20',
      badge: 'bg-rose-100 dark:bg-rose-950/50 text-rose-800 dark:text-rose-300'
    }
  ]

  const MAIN_QUESTION_OPTIONS = Array.from({ length: 6 }, (_, i) => i + 1) // Q1..Q6
  const PART_OPTIONS = ['-', 'a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j']
  const SUBPART_OPTIONS = [
    '-',
    'i',
    'ii',
    'iii',
    'iv',
    'v',
    'vi',
    'vii',
    'viii',
    'ix',
    'x',
    'xi',
    'xii',
    'xiii'
  ]

  const parseQuestionComponents = (label) => {
    if (!label) return { main: null, part: null, sub: null }
    const trimmed = label.trim()
    const mainMatch = trimmed.match(/^\s*[Qq]?(\d+)/)
    const main = mainMatch ? parseInt(mainMatch[1], 10) : null

    let part = null
    let sub = null

    // Look for patterns like "Q1 a i.)" or "Q1(a)(i)"
    const tokens = trimmed.split(/[\s().]+/).filter(Boolean)
    // tokens[0] is usually Q1 / 1
    if (tokens.length > 1) {
      const candidate = tokens[1].toLowerCase()
      if (/^[a-z]$/.test(candidate)) {
        part = candidate
      }
    }
    if (tokens.length > 2) {
      const candidate = tokens[2].toLowerCase()
      if (/^(i|ii|iii|iv|v)$/.test(candidate)) {
        sub = candidate
      }
    }
    return { main, part, sub }
  }

  const formatQuestionLabel = (main, part, sub) => {
    if (!main) return ''
    const pieces = [`Q${main}`]
    if (part && part !== '-') pieces.push(part)
    if (sub && sub !== '-') pieces.push(sub)
    return pieces.join(' ')
  }

  const computeNextQuestionTriple = (regionsList) => {
    // Determine next (main, part, sub) based on the last region in the ordered list
    if (!regionsList || regionsList.length === 0) {
      return { main: 1, part: 'a', sub: 'i' }
    }
    const last = regionsList[regionsList.length - 1]
    const lastLabel = last.question_number || ''
    const { main, part, sub } = parseQuestionComponents(lastLabel)
    const currentMain = main || 1
    const currentPart = part || 'a'

    // Helper to move to next valid element in an options array
    const nextIn = (arr, value) => {
      const idx = arr.indexOf(value)
      if (idx === -1) return value
      return arr[Math.min(idx + 1, arr.length - 1)]
    }

    // 1) If we already have a subpart (e.g. Q1 a i), advance sub within same main/part
    if (sub && sub !== '-' && sub !== SUBPART_OPTIONS[SUBPART_OPTIONS.length - 1]) {
      const nextSub = nextIn(SUBPART_OPTIONS, sub)
      return { main: currentMain, part: currentPart, sub: nextSub }
    }

    // 2) If we have a part but no sub (e.g. Q1 a -), advance part and keep sub empty ("-")
    if (sub == null || sub === '-') {
      if (currentPart && currentPart !== '-') {
        const nextPart = nextIn(PART_OPTIONS, currentPart)
        if (nextPart !== currentPart) {
          return { main: currentMain, part: nextPart, sub: '-' }
        }
      }
    }

    // 3) Otherwise bump main question, reset to a i (bounded by max)
    const nextMain = nextIn(MAIN_QUESTION_OPTIONS, currentMain)
    return { main: nextMain, part: 'a', sub: 'i' }
  }

  const parseMarksFromText = (text) => {
    if (!text) return null
    const match = text.match(/(\d+)\s*marks?/i)
    if (!match) return null
    const value = parseInt(match[1], 10)
    return Number.isNaN(value) ? null : value
  }

  const extractMarksAndClean = (text) => {
    if (!text) return { marks: null, cleanedText: text }
    // Capture patterns like "5 marks", "(5 marks)", "((( 5 marks )))", with any number of surrounding parentheses/spaces
    const match = text.match(/[()\s]*([0-9]+)\s*marks?[()\s]*/i)
    if (!match) return { marks: null, cleanedText: text }
    const marks = parseInt(match[1], 10)
    if (Number.isNaN(marks)) return { marks: null, cleanedText: text }
    // Remove the first occurrence of the matched "x mark(s)" (with any surrounding parentheses/spaces) from the text
    const cleanedText = text.replace(match[0], '').replace(/\s{2,}/g, ' ').trim()
    return { marks, cleanedText }
  }

  const regionColorMap = useMemo(() => {
    if (!regions?.length) return {}
    const rootToColor = {}
    const byId = {}
    regions.forEach((r, idx) => {
      const fallbackLabel = `Q${idx + 1}`
      const label = (r.question_number || fallbackLabel).trim()
      const m = label.match(/^\s*([Qq]?\d+)/)
      const root = (m ? m[1] : fallbackLabel).toUpperCase()
      if (!rootToColor[root]) {
        const paletteIndex = Object.keys(rootToColor).length % QUESTION_COLOR_PALETTE.length
        rootToColor[root] = QUESTION_COLOR_PALETTE[paletteIndex]
      }
      byId[r.id] = {
        ...rootToColor[root],
        label,
        root
      }
    })
    return byId
  }, [regions])

  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  // Load existing exam when opened from My Exams, or reset when opening "New Exam" (no state)
  useEffect(() => {
    const stateExamId = location.state?.examId
    const stateExamName = location.state?.examName
    const isRegrade = location.state?.regrade

    if (!stateExamId) {
      setExamId(null)
      setExamName('')
      setExamStatus(null)
      setStep(0)
      setUploadedDocs({ question: null, scheme: null, students: [] })
      setMarkingGuide([])
      setRegionCountByDocId({})
      setQuestionPaper(null)
      setAnswerScheme(null)
      setStudentAnswers([])
      return
    }

    setExamId(stateExamId)
    if (stateExamName) setExamName(stateExamName)

    let cancelled = false
    setLoading(true)
    setError('')

    Promise.all([
      examsAPI.get(stateExamId),
      documentsAPI.list(stateExamId, 'question_paper'),
      documentsAPI.list(stateExamId, 'answer_scheme'),
      documentsAPI.list(stateExamId, 'student_answer'),
      markingGuideAPI.get(stateExamId).catch(() => ({ data: [] }))
    ])
      .then(([examRes, qList, sList, stList, guideRes]) => {
        if (cancelled) return
        const exam = examRes.data
        if (exam?.name) setExamName(exam.name)
        if (exam?.status) setExamStatus(exam.status)
        const question = Array.isArray(qList.data) ? qList.data[0] : null
        const scheme = Array.isArray(sList.data) ? sList.data[0] : null
        const students = Array.isArray(stList.data) ? stList.data : []
        const guide = guideRes?.data ?? []

        setUploadedDocs({ question, scheme, students })
        setMarkingGuide(guide)

        // Decide which step to show when reopening:
        // - If there is an existing marking guide, always go to "Review Marking Guide" (step 2).
        //   This avoids landing on an unrendered step that appears as a blank screen.
        // - Else if question + students exist, go to "Process".
        // - Otherwise stay on "Upload".
        if (Array.isArray(guide) && guide.length > 0) {
          setStep(2)
        } else if (question && students.length > 0) {
          setStep(1)
        } else {
          setStep(0)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err?.response?.data?.detail ?? 'Failed to load exam')
          toast.error('Failed to load exam')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [location.state?.examId, location.state?.regrade])

  // Keep local drafts for answer guides in sync when marking guide changes
  useEffect(() => {
    if (!Array.isArray(markingGuide) || markingGuide.length === 0) {
      setAnswerGuideDrafts({})
      return
    }
    setAnswerGuideDrafts((prev) => {
      const next = { ...prev }
      markingGuide.forEach((q) => {
        if (next[q.id] == null) {
          next[q.id] = q.answer_scheme || ''
        }
      })
      return next
    })
  }, [markingGuide])

  // Sync region counts from backend (question paper + student docs) for step 1
  useEffect(() => {
    if (!examId) return
    const questionDoc = uploadedDocs.question
    const docsToSync = [...(questionDoc ? [questionDoc] : []), ...studentDocs]
    if (!docsToSync.length) return
    let cancelled = false
    const fetchCounts = async () => {
      const counts = {}
      await Promise.all(
        docsToSync.map(async (doc) => {
          try {
            const res = await documentsAPI.getRegions(doc.id)
            const list = res.data || []
            if (!cancelled) counts[doc.id] = list.length
          } catch {
            if (!cancelled) counts[doc.id] = 0
          }
        })
      )
      if (!cancelled) setRegionCountByDocId(counts)
    }
    fetchCounts()
    return () => { cancelled = true }
  }, [examId, studentDocs.length, uploadedDocs.question?.id])

  // Load all page images when modal opens (seamless scroll)
  useEffect(() => {
    if (!showRegionModal || !selectedDocId || !pages?.length) {
      setPageImageUrls((prev) => {
        Object.values(prev).forEach(URL.revokeObjectURL)
        return {}
      })
      return
    }
    let cancelled = false
    setLoadingPageImages(true)
    const pageNumbers = pages.map((p) => p.page_number)
    Promise.all(
      pageNumbers.map((pn) =>
        documentsAPI.getPageImage(selectedDocId, pn).then((res) => ({ pn, blob: res.data }))
      )
    )
      .then((results) => {
        if (cancelled) return
        setPageImageUrls((prev) => {
          Object.values(prev).forEach(URL.revokeObjectURL)
          const next = {}
          results.forEach(({ pn, blob }) => {
            next[pn] = URL.createObjectURL(blob)
          })
          return next
        })
      })
      .catch(() => {
        if (!cancelled) setPageImageUrls({})
      })
      .finally(() => {
        if (!cancelled) setLoadingPageImages(false)
      })
    return () => {
      cancelled = true
      setPageImageUrls((prev) => {
        Object.values(prev).forEach(URL.revokeObjectURL)
        return {}
      })
      setPageDimensions({})
    }
  }, [showRegionModal, selectedDocId, pages])

  // Document-level mouse move/up so crop completes when pointer is released outside the crop div
  useEffect(() => {
    if (!isCropping) return
    const onMove = (e) => {
      const img = cropImageRef.current
      if (!img) return
      const rect = img.getBoundingClientRect()
      const end = { x: e.clientX - rect.left, y: e.clientY - rect.top }
      cropEndRef.current = end
      setCropEnd(end)
    }
    const onUp = () => {
      const start = cropStartRef.current
      const end = cropEndRef.current
      const img = cropImageRef.current
      if (!start || !end || !img || !selectedDocId || !activePage) {
        setIsCropping(false)
        setCropStart(null)
        setCropEnd(null)
        cropStartRef.current = null
        cropEndRef.current = null
        return
      }
      setIsCropping(false)
      cropStartRef.current = null
      cropEndRef.current = null
      const displayWidth = img.clientWidth
      const displayHeight = img.clientHeight
      const naturalWidth = img.naturalWidth || displayWidth
      const naturalHeight = img.naturalHeight || displayHeight
      const scaleX = naturalWidth / displayWidth
      const scaleY = naturalHeight / displayHeight
      const x1 = Math.min(start.x, end.x) * scaleX
      const y1 = Math.min(start.y, end.y) * scaleY
      const x2 = Math.max(start.x, end.x) * scaleX
      const y2 = Math.max(start.y, end.y) * scaleY
      const w = Math.round(x2 - x1)
      const h = Math.round(y2 - y1)
      if (w < 2 || h < 2) {
        setCropStart(null)
        setCropEnd(null)
        return
      }
      // If cropping student answers, stop when we've reached the same count as question-paper regions
      if (
        selectedDocType === 'student_answer' &&
        questionTemplateRegions.length > 0 &&
        regions.length >= questionTemplateRegions.length
      ) {
        toast.error('You have already cropped all questions for this student answer.')
        setCropStart(null)
        setCropEnd(null)
        return
      }

      const payload = {
        page_number: activePage,
        x: Math.round(x1),
        y: Math.round(y1),
        width: w,
        height: h,
        region_type: selectedDocType || 'student_answer'
      }
      setCropStart(null)
      setCropEnd(null)
      setProcessingNewCrop(true)
      documentsAPI.saveCrop(selectedDocId, payload)
        .then((cropRes) => {
          const region = cropRes.data
          return processingAPI.runOCR(region.id).then((ocrRes) => ({
            region,
            raw_text: ocrRes.data?.raw_text ?? ocrRes.data?.text ?? region.raw_text
          }))
        })
        .then(async ({ region, raw_text }) => {
          const { marks, cleanedText } = extractMarksAndClean(raw_text || '')
          const finalText = cleanedText ?? raw_text
          const basePayload = { raw_text: finalText, marks }
          await processingAPI.updateRegionText(region.id, basePayload).catch(() => {})
          const cleanupResult = await maybeCleanupExtractedText(region.id, finalText)
          const postCleanText = cleanupResult.text ?? finalText

          setRegions(prev => {
            let question_number = region.question_number
            if (selectedDocType === 'question') {
              // Auto-assign sequential question numbers for question paper
              const { main, part, sub } = computeNextQuestionTriple(prev)
              question_number = formatQuestionLabel(main, part, sub)
            } else if (selectedDocType === 'student_answer' && questionTemplateRegions.length > 0) {
              // For student answers, follow the question order from the question paper template
              const template = questionTemplateRegions[Math.min(prev.length, questionTemplateRegions.length - 1)]
              if (template?.question_number) {
                question_number = template.question_number
              }
            }
            const nextRegion = {
              ...region,
              question_number,
              raw_text: postCleanText,
              marks
            }
            // Persist cleaned text, marks and question_number (if any)
            const payloadUpdate = { raw_text: postCleanText, marks }
            if (question_number) payloadUpdate.question_number = question_number
            processingAPI.updateRegionText(region.id, payloadUpdate).catch(() => {})
            return [...prev, nextRegion]
          })
          markDocCropped(selectedDocId)
          toast.success('Answer region cropped and processed')
        })
        .catch((err) => {
          const detail = err?.response?.data?.detail ?? err?.message
          toast.error(typeof detail === 'string' ? detail : 'Failed to crop or run OCR for this region')
        })
        .finally(() => setProcessingNewCrop(false))
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
    return () => {
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
  }, [isCropping, selectedDocId, activePage, selectedDocType, regions.length, questionTemplateRegions.length, autoCleanupEnabled])

  // Drag handlers
  const handleDrag = useCallback((e, zone) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(zone)
    } else if (e.type === 'dragleave') {
      setDragActive(null)
    }
  }, [])

  const handleDrop = useCallback((e, setter, multiple = false, acceptedExts = ['.pdf']) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(null)
    const normalizedExts = new Set((acceptedExts || []).map((ext) => ext.toLowerCase()))
    const files = Array.from(e.dataTransfer.files).filter((f) => {
      const name = (f?.name || '').toLowerCase()
      const ext = name.includes('.') ? `.${name.split('.').pop()}` : ''
      return normalizedExts.has(ext)
    })
    if (files.length > 0) {
      if (multiple) {
        setter(prev => [...prev, ...files])
      } else {
        setter(files[0])
      }
    }
  }, [])

  const removeStudentFile = (index) => {
    setStudentAnswers(prev => prev.filter((_, i) => i !== index))
  }

  const resolveFrontendBaseUrl = () => {
    if (typeof window === 'undefined') return ''
    const host = window.location.hostname
    const protocol = window.location.protocol
    if (host === 'localhost' || host === '127.0.0.1') {
      return `${protocol}//${host}:5173`
    }
    return `${protocol}//${window.location.host}`
  }

  const refreshUploadedDocs = async (targetExamId) => {
    const [qList, sList, stList] = await Promise.all([
      documentsAPI.list(targetExamId, 'question_paper'),
      documentsAPI.list(targetExamId, 'answer_scheme'),
      documentsAPI.list(targetExamId, 'student_answer')
    ])
    const question = Array.isArray(qList.data) ? qList.data[0] : null
    const scheme = Array.isArray(sList.data) ? sList.data[0] : null
    const students = Array.isArray(stList.data) ? stList.data : []
    setUploadedDocs({ question, scheme, students })
    return { question, scheme, students }
  }

  const ensureExamForCapture = async () => {
    if (examId) return examId
    if (!examName.trim()) throw new Error('Enter an exam name first')
    const examRes = await examsAPI.create({ name: examName })
    const newExamId = examRes.data.id
    setExamId(newExamId)
    return newExamId
  }

  const closeCaptureDialog = () => {
    setCaptureDialog({ open: false, loading: false, docType: null, url: '', sessionId: '', expiresAt: null })
  }

  const openCaptureDialog = async (docType) => {
    setError('')
    setCaptureDialog({ open: true, loading: true, docType, url: '', sessionId: '', expiresAt: null })
    try {
      const targetExamId = await ensureExamForCapture()
      const frontendBaseUrl = resolveFrontendBaseUrl()
      const res = await captureAPI.createSession(targetExamId, docType, frontendBaseUrl)
      const data = res?.data || {}
      setCaptureDialog({
        open: true,
        loading: false,
        docType,
        url: data.mobile_url || '',
        sessionId: data.session_id || '',
        expiresAt: data.expires_at || null
      })
    } catch (err) {
      closeCaptureDialog()
      setError(err?.response?.data?.detail || err?.message || 'Failed to start phone capture')
    }
  }

  useEffect(() => {
    if (!captureDialog.open || !captureDialog.sessionId || !examId) return undefined
    const interval = setInterval(async () => {
      try {
        const statusRes = await captureAPI.getSessionOwner(examId, captureDialog.sessionId)
        const status = statusRes?.data?.status
        if (status === 'completed') {
          await refreshUploadedDocs(examId)
          setStudentAnswers([])
          if (captureDialog.docType === 'question_paper') setQuestionPaper(null)
          closeCaptureDialog()
          toast.success('Phone capture uploaded successfully')
        }
      } catch {
        // Ignore transient polling failures.
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [captureDialog.open, captureDialog.sessionId, captureDialog.docType, examId])

  // Step 1: Upload
  const handleUpload = async () => {
    if (!examName.trim()) {
      setError('Please enter an exam name')
      return
    }
    const hasQuestion = !!uploadedDocs.question || !!questionPaper
    const hasStudents = (uploadedDocs.students?.length || 0) + studentAnswers.length > 0
    // Answer scheme is optional – only require question paper and at least one student answer
    if (!hasQuestion || !hasStudents) {
      setError('Please upload a question paper and at least one student answer sheet')
      return
    }

    setLoading(true)
    setError('')

    try {
      let targetExamId = examId
      if (!targetExamId) {
        const examRes = await examsAPI.create({ name: examName })
        targetExamId = examRes.data.id
        setExamId(targetExamId)
      }

      if (questionPaper) {
        await documentsAPI.upload(targetExamId, questionPaper, 'question_paper')
      }
      if (answerScheme) {
        await documentsAPI.upload(targetExamId, answerScheme, 'answer_scheme')
      }
      if (studentAnswers.length > 0) {
        await documentsAPI.uploadMultiple(targetExamId, studentAnswers, 'student_answer')
      }

      await refreshUploadedDocs(targetExamId)
      setQuestionPaper(null)
      setAnswerScheme(null)
      setStudentAnswers([])

      toast.success('Documents uploaded successfully!')
      setStep(1)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  // Step 2: Process (non-blocking: start in background, optional poll to advance when done)
  const handleProcess = async () => {
    setError('')
    setProcessing(true)
    setProcessStatus('Building marking guide from cropped question paper...')
    try {
      if (!examId || !uploadedDocs.question?.id) {
        throw new Error('Question paper is missing for this exam')
      }

      // Load existing marking guide and clear it (we'll regenerate from cropped question regions)
      let existingGuide = []
      try {
        const existingRes = await markingGuideAPI.get(examId)
        existingGuide = Array.isArray(existingRes.data) ? existingRes.data : []
      } catch {
        existingGuide = []
      }

      const existingGuideByQNum = new Map(
        existingGuide
          .map((q) => [String(q.question_number || '').trim(), q])
          .filter(([qNum]) => qNum.length > 0)
      )

      if (existingGuide.length > 0) {
        await Promise.all(
          existingGuide.map((q) =>
            markingGuideAPI.deleteQuestion(q.id).catch(() => {})
          )
        )
      }

      // Load cropped regions from the question paper and turn them into marking guide questions
      const regionsRes = await documentsAPI.getRegions(uploadedDocs.question.id)
      const regionList = Array.isArray(regionsRes.data) ? regionsRes.data : []

      const newGuide = []
      for (const r of regionList) {
        const originalQNum = (r.question_number || '').trim()
        const question_number = originalQNum || String(newGuide.length + 1)
        const question_text = (r.processed_text || r.raw_text || '').trim()
        const rawMarks = r.marks
        const max_marks = rawMarks ?? 0
        const prevGuide = existingGuideByQNum.get(question_number)

        // Skip regions that have no meaningful content:
        // - no OCR text
        // - no explicit question number set on the region
        // - and no non-zero marks
        const hasText = !!question_text
        const hasExplicitQNum = !!originalQNum
        const hasMarks = rawMarks != null && Number(rawMarks) !== 0
        if (!hasText && !hasExplicitQNum && !hasMarks) continue

        const payload = {
          question_number,
          question_text,
          question_type: 'structured',
          max_marks,
          // Preserve teacher-authored guide data when question number matches.
          answer_scheme: prevGuide?.answer_scheme || '',
          keypoint_marks: prevGuide?.keypoint_marks || ''
        }

        try {
          const created = await markingGuideAPI.addQuestion(examId, payload)
          newGuide.push(created.data)
        } catch {
          // Ignore individual failures, continue with others
        }
      }

      setMarkingGuide(newGuide)
      setExamStatus('draft')
      toast.success('Marking guide template created from cropped question paper')
      // Move directly to the Marking Guide step where the user can review/edit.
      setStep(2)
      setProcessStatus('')
      setProcessing(false)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Processing failed')
      setProcessStatus('')
      setProcessing(false)
    }
  }

  const processingPollRef = useRef(null)
  const startProcessingPoll = () => {
    if (processingPollRef.current) return
    processingPollRef.current = setInterval(async () => {
      if (!examId) return
      try {
        const res = await examsAPI.get(examId)
        if (res.data?.status === 'draft') {
          setExamStatus('draft')
          stopProcessingPoll()
          toast.success('Processing complete')
          setStep(2)
        }
      } catch {
        // ignore
      }
    }, 3000)
  }
  const stopProcessingPoll = () => {
    if (processingPollRef.current) {
      clearInterval(processingPollRef.current)
      processingPollRef.current = null
    }
  }
  useEffect(() => {
    return () => stopProcessingPoll()
  }, [examId])

  // --- Regions View ---
  const handleViewRegions = async (docId, docType = 'student_answer') => {
    setSelectedDocId(docId)
    setSelectedDocType(docType)
    setLoadingRegions(true)
    setShowRegionModal(true)
    setError('')
    try {
      // Load pages first (must exist for cropping)
      const pagesRes = await documentsAPI.getPages(docId)
      const docPages = pagesRes.data?.pages || []
      setPages(docPages)
      setActivePage(docPages[0]?.page_number || null)

      // Then try to load any existing regions.
      // If the API returns 404, we treat it as "no regions yet" instead of an error.
      try {
        const regionsRes = await documentsAPI.getRegions(docId)
        const list = regionsRes.data || []
        setRegions(
          list.map((r) => ({
            ...r,
            // Prefer marks already saved in DB; only fall back to parsing if absent
            marks:
              r.marks != null
                ? r.marks
                : parseMarksFromText(r.processed_text || r.raw_text)
          }))
        )

        // If viewing the question paper, remember its regions as the template order
        if (docType === 'question') {
          setQuestionTemplateRegions(list)
        }
      } catch (err) {
        if (err?.response?.status === 404) {
          setRegions([])
        } else {
          throw err
        }
      }

      // When cropping student answers, always refresh the question-paper template
      // so the latest edited question numbers are used for new/re-scanned crops.
      if (docType === 'student_answer' && uploadedDocs.question?.id) {
        try {
          const qRegionsRes = await documentsAPI.getRegions(uploadedDocs.question.id)
          const qList = qRegionsRes.data || []
          setQuestionTemplateRegions(qList)
        } catch {
          // ignore; student regions can still be edited manually if needed
        }
      }
    } catch (err) {
      toast.error('Failed to load document regions')
      setShowRegionModal(false)
    } finally {
      setLoadingRegions(false)
    }
  }

  const markDocCropped = (docId) => {
    if (!docId) return
    setRegionCountByDocId(prev => ({ ...prev, [docId]: (prev[docId] ?? 0) + 1 }))
  }

  const maybeCleanupExtractedText = async (regionId, fallbackText) => {
    if (!autoCleanupEnabled || selectedDocType !== 'question') {
      return { text: fallbackText, changed: false, provider: null, model: null, fallbackUsed: false }
    }
    try {
      const res = await processingAPI.cleanupText(regionId)
      const cleaned = (res?.data?.processed_text || '').trim()
      const nextText = cleaned || fallbackText
      const meta = {
        changed: Boolean(res?.data?.changed),
        provider: res?.data?.provider || 'ollama',
        model: res?.data?.model || '',
        fallbackUsed: Boolean(res?.data?.fallback_used),
        processed: true
      }
      setRegionCleanupMeta(prev => ({ ...prev, [regionId]: meta }))
      return { text: nextText, ...meta }
    } catch {
      const meta = {
        changed: false,
        provider: 'ollama',
        model: '',
        fallbackUsed: true,
        processed: false
      }
      setRegionCleanupMeta(prev => ({ ...prev, [regionId]: meta }))
      return { text: fallbackText, ...meta }
    }
  }

  const handleRunOcr = async (regionId) => {
    setRunningOcrFor(regionId)
    try {
      const res = await processingAPI.runOCR(regionId)
      const target = regions.find((r) => r.id === regionId)
      const newText = res.data?.raw_text ?? res.data?.text ?? target?.raw_text
      const { marks, cleanedText } = extractMarksAndClean(newText || '')
      const finalText = cleanedText ?? newText
      await processingAPI.updateRegionText(regionId, { raw_text: finalText, marks }).catch(() => {})
      const cleanupResult = await maybeCleanupExtractedText(regionId, finalText)
      const postCleanText = cleanupResult.text ?? finalText

      setRegions(prev => prev.map(r => (
        r.id === regionId
          ? {
              ...r,
              raw_text: postCleanText,
              marks
            }
          : r
      )))
      toast.success('OCR ran successfully')
    } catch (err) {
      toast.error('Failed to run OCR for this region')
    } finally {
      setRunningOcrFor(null)
    }
  }

  const handleDeleteRegion = async (regionId) => {
    try {
      await processingAPI.deleteRegion(regionId)
      const wasOnly = regions.length === 1
      setRegions(prev => prev.filter(r => r.id !== regionId))
      if (selectedDocId) {
        setRegionCountByDocId(prev => ({
          ...prev,
          [selectedDocId]: Math.max(0, (prev[selectedDocId] ?? 0) - 1)
        }))
      }
      toast.success('Region removed')
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Failed to delete region')
    }
  }

  const handleUpdateRegionText = async (regionId, rawText) => {
    try {
      await processingAPI.updateRegionText(regionId, { raw_text: rawText })
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Failed to save edit')
    }
  }

  const saveRegionsProgress = async (docId, regionsList) => {
    if (!docId || !regionsList?.length) return
    try {
      await documentsAPI.saveRegionsOrder(docId, regionsList.map((r) => r.id))
      await Promise.all(
        regionsList.map((r) =>
          processingAPI
            .updateRegionText(r.id, {
              raw_text: r.raw_text ?? '',
              marks: r.marks ?? null,
              question_number: r.question_number ?? null
            })
            .catch(() => {})
        )
      )
    } catch (err) {
      toast.error(err?.response?.data?.detail ?? 'Failed to save progress')
    }
  }

  const handleCloseRegionModal = async () => {
    if (selectedDocId && regions.length > 0) {
      await saveRegionsProgress(selectedDocId, regions)
    }
    if (selectedDocId) {
      setRegionCountByDocId(prev => ({ ...prev, [selectedDocId]: regions.length }))
    }
    setShowRegionModal(false)
  }

  // Step 3: Generate Marking Guide
  const handleGenerateGuide = async () => {
    setLoading(true)
    setError('')
    toast.info('Generating marking guide... This may take a minute.')

    try {
      const res = await markingGuideAPI.generate(examId)
      setMarkingGuide(res.data.marking_guide || [])
      toast.success('Marking guide generated!')
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate marking guide')
      toast.error('Failed to generate marking guide')
    } finally {
      setLoading(false)
    }
  }

  const updateGuideQuestion = async (index, field, value) => {
    const guide = markingGuide[index]
    const updated = { ...guide, [field]: value }

    try {
      await markingGuideAPI.updateQuestion(guide.id, { [field]: value })
      const newGuide = [...markingGuide]
      newGuide[index] = updated
      setMarkingGuide(newGuide)
    } catch (err) {
      toast.error('Failed to update question')
    }
  }

  const handleAddQuestion = async () => {
    try {
      const res = await markingGuideAPI.addQuestion(examId, {
        question_number: String(markingGuide.length + 1),
        question_text: '',
        question_type: 'structured',
        max_marks: 1,
        answer_scheme: ''
      })
      setMarkingGuide([...markingGuide, res.data])
      toast.info('Question added')
    } catch (err) {
      toast.error('Failed to add question')
    }
  }

  // Step 4: Start Grading
  const handleStartGrading = async () => {
    setLoading(true)
    setError('')

    try {
      const provider = (gradingProvider || 'ollama').trim()
      const model = (gradingModel || '').trim()
      const payload = { provider }
      // OpenRouter only; Ollama always uses server OLLAMA_MODEL — never send model.
      if (provider === 'openrouter' && model) {
        payload.model = model
      }
      await gradingAPI.start(examId, payload)
      toast.success('Grading started! Check the Exam List for progress.')
      navigate('/exams')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start grading')
    } finally {
      setLoading(false)
    }
  }

  const FileDropZone = ({ id, label, subtitle, file, onFileChange, onDrop, zone, accept = '.pdf', multiple = false }) => (
    <div
      onDragEnter={(e) => handleDrag(e, zone)}
      onDragLeave={(e) => handleDrag(e, zone)}
      onDragOver={(e) => handleDrag(e, zone)}
      onDrop={(e) => onDrop(e)}
      className={`drop-zone relative ${dragActive === zone ? 'active' : ''}`}
    >
      <input
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={onFileChange}
        className="hidden"
        id={id}
      />
      <label htmlFor={id} className="cursor-pointer block">
        <div className="flex flex-col items-center gap-2">
          <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
            file ? 'bg-emerald-100' : 'bg-gray-100'
          }`}>
            {file ? (
              <svg className="w-6 h-6 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            ) : (
              <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            )}
          </div>
          <h3 className="font-semibold text-gray-700 dark:text-slate-300">{label}</h3>
          {file ? (
            <span className="text-sm text-emerald-600 font-medium">
              {typeof file === 'object' && file.name ? file.name : `${file} files selected`}
            </span>
          ) : (
            <span className="text-sm text-gray-400 dark:text-slate-500">{subtitle}</span>
          )}
        </div>
      </label>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Grade Paper</h1>
        <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Upload, process, and grade exam papers with AI</p>
      </div>

      {/* Step Indicator */}
      <div className="card-flat p-4">
        <div className="flex items-center justify-between">
          {STEPS.map((s, i) => (
            <div key={s.label} className="flex items-center flex-1">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-sm font-semibold transition-all duration-300 ${
                  i < step ? 'bg-emerald-100 text-emerald-700' :
                  i === step ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/25' :
                  'bg-gray-100 dark:bg-slate-800 text-gray-400 dark:text-slate-500'
                }`}>
                  {i < step ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <StepIcon name={s.icon} className="w-5 h-5" />
                  )}
                </div>
                <span className={`text-sm font-medium hidden sm:block ${
                  i <= step ? 'text-gray-900 dark:text-slate-100' : 'text-gray-400 dark:text-slate-500'
                }`}>{s.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-4 rounded-full transition-colors ${
                  i < step ? 'bg-emerald-400' : 'bg-gray-200 dark:bg-slate-600'
                }`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm animate-fade-in">
          <svg className="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {error}
          <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-600">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {/* Step 1: Upload */}
      {step === 0 && (
        <div className="card p-6 space-y-6 animate-fade-in">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1.5">Exam Name</label>
            <input
              type="text"
              value={examName}
              onChange={(e) => setExamName(e.target.value)}
              className="input-field"
              placeholder="e.g., Mid-Term Exam 2024"
            />
          </div>

          <div className="grid grid-cols-1 gap-4">
            <FileDropZone
              id="question-paper"
              label="Question Paper"
              subtitle="Drop PDF or click to browse"
              file={questionPaper || (uploadedDocs.question
                ? { name: uploadedDocs.question.file_name || 'Captured question paper.pdf' }
                : null)}
              onFileChange={(e) => setQuestionPaper(e.target.files[0])}
              onDrop={(e) => handleDrop(e, setQuestionPaper)}
              zone="question"
            />
            <button
              type="button"
              onClick={() => openCaptureDialog('question_paper')}
              className="btn-secondary w-full"
              disabled={captureDialog.loading}
            >
              Scan Question Paper from Phone
            </button>
          </div>

          <div>
            <FileDropZone
              id="student-answers"
              label="Student Answer Sheets"
              subtitle="Drop multiple PDFs or ZIP files or click to browse"
              file={
                studentAnswers.length > 0
                  ? `${studentAnswers.length}`
                  : ((uploadedDocs.students?.length || 0) > 0 ? `${uploadedDocs.students.length}` : null)
              }
              onFileChange={(e) => {
                const files = Array.from(e.target.files || []).filter((file) => {
                  const name = (file?.name || '').toLowerCase()
                  return name.endsWith('.pdf') || name.endsWith('.zip')
                })
                setStudentAnswers(prev => [...prev, ...files])
              }}
              onDrop={(e) => handleDrop(e, setStudentAnswers, true, ['.pdf', '.zip'])}
              zone="students"
              accept=".pdf,.zip"
              multiple
            />
            <button
              type="button"
              onClick={() => openCaptureDialog('student_answer')}
              className="btn-secondary w-full mt-3"
              disabled={captureDialog.loading}
            >
              Scan Student Answer from Phone
            </button>
            {studentAnswers.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {studentAnswers.map((file, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 dark:bg-slate-800/80 rounded-lg text-sm border border-transparent dark:border-slate-700">
                    <svg className="w-4 h-4 text-gray-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <span className="text-gray-600 dark:text-slate-300 truncate max-w-[150px]">{file.name}</span>
                    <button
                      onClick={() => removeStudentFile(i)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
            {(uploadedDocs.students?.length || 0) > 0 && studentAnswers.length === 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {uploadedDocs.students.slice(0, 8).map((doc) => (
                  <div key={doc.id} className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 dark:bg-slate-800/80 rounded-lg text-sm border border-transparent dark:border-slate-700">
                    <svg className="w-4 h-4 text-gray-400 dark:text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <span className="text-gray-600 dark:text-slate-300 truncate max-w-[170px]">
                      {doc.file_name || 'Captured student PDF'}
                    </span>
                  </div>
                ))}
                {uploadedDocs.students.length > 8 && (
                  <div className="flex items-center px-3 py-1.5 rounded-lg text-xs text-gray-500 bg-gray-50 dark:bg-slate-800/80 border border-transparent dark:border-slate-700">
                    +{uploadedDocs.students.length - 8} more
                  </div>
                )}
              </div>
            )}
          </div>

          <button
            onClick={handleUpload}
            disabled={loading}
            className="w-full btn-primary py-3 flex justify-center items-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Uploading...
              </>
            ) : (
              <>
                Next: Process Documents
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </>
            )}
          </button>
        </div>
      )}

      {/* Step 2: Process */}
      {step === 1 && (
        <div className="card p-6 space-y-6 animate-fade-in">
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Process Documents</h2>

          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-indigo-50/50 dark:bg-indigo-950/40 rounded-xl p-4 border border-indigo-100 dark:border-indigo-900/50">
              <p className="text-xs font-medium text-indigo-500 uppercase tracking-wide">Question Paper</p>
              <p className="text-2xl font-bold text-indigo-700 mt-1">{uploadedDocs.question?.page_count || 0}</p>
              <p className="text-xs text-indigo-400">pages</p>
            </div>
            <div className="bg-emerald-50/50 dark:bg-emerald-950/40 rounded-xl p-4 border border-emerald-100 dark:border-emerald-900/50">
              <p className="text-xs font-medium text-emerald-500 uppercase tracking-wide">Student Answers</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{uploadedDocs.students?.length || 0}</p>
              <p className="text-xs text-emerald-400">files</p>
            </div>
          </div>

          {processing && (
            <div className="flex flex-col items-center py-8 gap-4">
              <div className="relative">
                <div className="animate-spin rounded-full h-14 w-14 border-4 border-indigo-100 border-t-indigo-600"></div>
              </div>
              <p className="text-sm font-medium text-gray-600 dark:text-slate-400">{processStatus}</p>
              <div className="w-full max-w-xs progress-bar">
                <div className="progress-bar-fill" style={{ width: '60%' }} />
              </div>
            </div>
          )}

          {!processing && uploadedDocs.question && (
            <div className="mt-6 border-t border-gray-100 dark:border-slate-700 pt-6">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100 mb-1">Crop Question Paper</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                <button
                  onClick={() => handleViewRegions(uploadedDocs.question.id, 'question')}
                  className="text-left p-3 rounded-xl border border-gray-200 dark:border-slate-600 hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/30 transition-all group flex items-center justify-between"
                >
                  <div className="flex items-center gap-2 overflow-hidden">
                    <svg className="w-5 h-5 text-gray-400 group-hover:text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <div className="flex flex-col">
                      <span className="text-sm font-medium text-gray-700 dark:text-slate-300 truncate">Question paper</span>
                      <span className={`text-[11px] font-medium ${(regionCountByDocId[uploadedDocs.question.id] ?? 0) > 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                        {(regionCountByDocId[uploadedDocs.question.id] ?? 0) > 0
                          ? `${regionCountByDocId[uploadedDocs.question.id]} region(s) cropped ✅`
                          : 'Not cropped yet'}
                      </span>
                    </div>
                  </div>
                  <svg className="w-4 h-4 text-gray-300 group-hover:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {!processing && studentDocs.length > 0 && (
            <div className="mt-6 border-t border-gray-100 pt-6">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900 dark:text-slate-100">Crop Student Answer</h3>
                  <p className="text-xs font-medium text-gray-600">
                    Progress: {croppedStudentCount} / {studentDocs.length} students cropped
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    ref={addStudentInputRef}
                    type="file"
                    accept=".pdf,.zip"
                    multiple
                    className="hidden"
                    onChange={async (e) => {
                      const files = Array.from(e.target.files || []).filter((file) => {
                        const name = (file?.name || '').toLowerCase()
                        return name.endsWith('.pdf') || name.endsWith('.zip')
                      })
                      e.target.value = ''
                      if (!examId || files.length === 0) return
                      try {
                        setLoading(true)
                        const res = await documentsAPI.uploadMultiple(examId, files, 'student_answer')
                        setUploadedDocs((prev) => ({
                          ...prev,
                          students: [...(prev.students || []), ...(res.data || [])]
                        }))
                        toast.success('Student answer sheets added')
                      } catch (err) {
                        toast.error(err?.response?.data?.detail || 'Failed to add student answers')
                      } finally {
                        setLoading(false)
                      }
                    }}
                  />
                  <button
                    type="button"
                    onClick={() => addStudentInputRef.current?.click()}
                    className="btn-secondary px-3 py-1.5 text-xs"
                  >
                    Add
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {studentDocs
                  .slice()
                  .sort((a, b) => {
                    const aDone = croppedDocs.has(a.id)
                    const bDone = croppedDocs.has(b.id)
                    if (aDone === bDone) return (a.file_name || '').localeCompare(b.file_name || '')
                    return aDone ? 1 : -1
                  })
                  .map((doc) => (
                    <div
                      key={doc.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => handleViewRegions(doc.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          handleViewRegions(doc.id)
                        }
                      }}
                      className="relative text-left p-3 rounded-xl border border-gray-200 dark:border-slate-600 hover:border-indigo-400 dark:hover:border-indigo-500 hover:bg-indigo-50/30 dark:hover:bg-indigo-950/30 transition-all group flex items-center justify-between cursor-pointer outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-900"
                    >
                      <div className="flex items-center gap-2 overflow-hidden pr-6">
                        <svg className="w-5 h-5 text-gray-400 group-hover:text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <div className="flex flex-col">
                          <span className="text-sm font-medium text-gray-700 dark:text-slate-300 truncate">
                            {doc.file_name || 'Student Document'}
                          </span>
                          <span className={`text-[11px] font-medium ${
                            croppedDocs.has(doc.id) ? 'text-emerald-600' : 'text-amber-600'
                          }`}>
                            {(regionCountByDocId[doc.id] ?? 0) > 0
                              ? `${regionCountByDocId[doc.id]} answer${regionCountByDocId[doc.id] !== 1 ? 's' : ''} cropped ✅`
                              : 'Not cropped yet'}
                          </span>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (!window.confirm('Remove this student answer sheet? This will also delete its cropped regions.')) {
                            return
                          }
                          documentsAPI
                            .delete(doc.id)
                            .then(() => {
                              setUploadedDocs((prev) => ({
                                ...prev,
                                students: (prev.students || []).filter((s) => s.id !== doc.id)
                              }))
                              setRegionCountByDocId((prev) => {
                                const next = { ...prev }
                                delete next[doc.id]
                                return next
                              })
                              toast.success('Student answer sheet removed')
                            })
                            .catch((err) => {
                              toast.error(err?.response?.data?.detail || 'Failed to remove student answer sheet')
                            })
                        }}
                        className="absolute top-1 right-1 p-1 rounded-full bg-white/80 text-gray-400 hover:text-red-600 hover:bg-red-50 shadow-sm transition-colors"
                        title="Remove student answer sheet"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={handleProcess}
              disabled={processing || examStatus === 'processing' || !allStudentsCropped}
              className="flex-1 btn-primary py-3 flex justify-center items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {(processing || examStatus === 'processing') ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  {examStatus === 'processing' ? 'Processing in background...' : 'Processing...'}
                </>
              ) : (
                <>
                  Start Processing
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </>
              )}
            </button>
          </div>
          {(!processing && examStatus !== 'processing' && studentDocs.length > 0 && !allStudentsCropped) && (
            <p className="text-xs text-amber-600 mt-2">
              Please crop at least one answer region for each student document before starting processing.
            </p>
          )}
          {examStatus === 'processing' && (
            <p className="text-xs text-gray-500 mt-2">
              Processing is running in the background. You can stay on this page or navigate away.
            </p>
          )}
        </div>
      )}

      {/* Step 3: Review Marking Guide */}
      {step === 2 && (
        <div className="card p-6 space-y-6 animate-fade-in">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Review Marking Guide</h2>
              <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">Edit questions, types, and marks as needed.</p>
            </div>
            <button
              type="button"
              onClick={() => setStep(1)}
              className="px-4 py-2.5 text-sm font-semibold rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-500/25 hover:bg-indigo-700 active:bg-indigo-800 active:scale-[0.99] transition-all duration-200"
            >
              Back to Process Documents
            </button>
          </div>

          {markingGuide.length === 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
              <svg className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
              <div>
                <p className="text-sm font-medium text-amber-800">No questions generated</p>
                <p className="text-sm text-amber-700 mt-0.5">
                  The AI may not have returned a structured list, or the question paper/answer scheme text was empty. Generate the guide again to populate questions.
                </p>
              </div>
            </div>
          )}
          <div className="overflow-x-auto rounded-xl border border-gray-100">
            <table className="w-full">
              <thead>
                <tr className="table-header">
                  <th className="px-4 py-3 text-left">Q.No</th>
                  <th className="px-4 py-3 text-left">Question</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Marks</th>
                </tr>
              </thead>
              <tbody>
                {markingGuide.map((q, i) => {
                  const answerGuideDraft =
                    answerGuideDrafts[q.id] ?? q.answer_scheme ?? ''
                  const answerGuideSaved = q.answer_scheme ?? ''
                  const answerGuideUnsaved = answerGuideDraft !== answerGuideSaved
                  return (
                  <React.Fragment key={q.id}>
                    <tr className="table-row align-top">
                      <td className="px-4 py-3">
                        <span className="inline-flex items-center justify-center w-16 px-2 py-1.5 rounded-lg text-sm font-medium text-gray-800 dark:text-slate-200 bg-gray-50 dark:bg-slate-800 border border-gray-100 dark:border-slate-600">
                          {q.question_number}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          value={q.question_text || ''}
                          onChange={(e) => updateGuideQuestion(i, 'question_text', e.target.value)}
                          className="w-full px-2 py-1.5 border border-gray-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-indigo-500 focus:border-indigo-500"
                          placeholder="Enter question text..."
                        />
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={q.question_type || 'structured'}
                          onChange={(e) => updateGuideQuestion(i, 'question_type', e.target.value)}
                          className="px-2 py-1.5 border border-gray-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-indigo-500 focus:border-indigo-500"
                        >
                          <option value="structured">Structured</option>
                          <option value="mcq">MCQ</option>
                          <option value="open_ended">Open-ended</option>
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <input
                          type="number"
                          value={q.max_marks || 0}
                          onChange={(e) => updateGuideQuestion(i, 'max_marks', parseFloat(e.target.value))}
                          className="w-20 px-2 py-1.5 border border-gray-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-indigo-500 focus:border-indigo-500"
                        />
                      </td>
                    </tr>
                    <tr className="bg-gray-50/60 dark:bg-slate-800/50">
                      <td className="px-4 pt-1 pb-2 text-left align-top text-[11px] font-medium text-gray-500 dark:text-slate-400">
                        Answer guide
                      </td>
                      <td className="px-4 py-2 align-top" colSpan={4}>
                        <div className="relative group">
                          <textarea
                            value={answerGuideDraft}
                            onChange={(e) =>
                              setAnswerGuideDrafts((prev) => ({
                                ...prev,
                                [q.id]: e.target.value
                              }))
                            }
                            rows={6}
                            className={`w-full min-h-[120px] px-3 py-2 pr-16 rounded-lg text-sm resize-y bg-white dark:bg-slate-800 text-neutral-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 ${
                              answerGuideUnsaved
                                ? 'answer-guide-unsaved border-2 border-yellow-400 focus:ring-2 focus:ring-yellow-400/45 focus:border-yellow-500'
                                : 'border border-gray-200 dark:border-slate-600 focus:ring-indigo-500 focus:border-indigo-500'
                            }`}
                            placeholder="Describe the ideal/correct answer, key points, marking notes..."
                          />
                          {savingAnswerGuideId === q.id ? (
                            <span className="absolute bottom-2 right-3 text-[11px] text-gray-400 select-none">
                              Saving...
                            </span>
                          ) : answerGuideUnsaved ? (
                            <button
                              type="button"
                              onClick={async () => {
                                const draft = answerGuideDrafts[q.id] ?? ''
                                setSavingAnswerGuideId(q.id)
                                try {
                                  const res = await markingGuideAPI.updateQuestion(q.id, {
                                    answer_scheme: draft
                                  })
                                  setMarkingGuide((prev) =>
                                    prev.map((g) => (g.id === q.id ? res.data : g))
                                  )
                                  setAnswerGuideDrafts((prev) => ({
                                    ...prev,
                                    [q.id]: res.data.answer_scheme || ''
                                  }))
                                  toast.success('Answer guide saved')
                                } catch (err) {
                                  toast.error(
                                    err?.response?.data?.detail || 'Failed to save answer guide'
                                  )
                                } finally {
                                  setSavingAnswerGuideId(null)
                                }
                              }}
                              className="absolute bottom-2 right-2 px-2.5 py-1 text-[11px] font-medium rounded-md border border-indigo-200 bg-indigo-50 text-indigo-700 shadow-sm opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity"
                            >
                              Save
                            </button>
                          ) : null}
                        </div>
                      </td>
                    </tr>
                  </React.Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between items-center pt-2">
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600 dark:text-slate-300">
                {markingGuide.length} questions
              </span>
              <span className="text-sm font-semibold text-gray-800 dark:text-slate-100 bg-gray-100 dark:bg-slate-700 border border-gray-200 dark:border-slate-600 px-3 py-1 rounded-full">
                Total: {markingGuide.reduce((sum, q) => sum + (q.max_marks || 0), 0)} marks
              </span>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <select
                value={gradingProvider}
                onChange={(e) => {
                  const v = e.target.value
                  setGradingProvider(v)
                  if (v === 'ollama') setGradingModel('')
                }}
                className="px-3 py-2 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              >
                <option value="ollama">Ollama (local)</option>
                <option value="openrouter">OpenRouter</option>
              </select>
              {gradingProvider === 'openrouter' ? (
                <input
                  type="text"
                  value={gradingModel}
                  onChange={(e) => setGradingModel(e.target.value)}
                  placeholder="Default: Auto select best model"
                  className="w-72 px-3 py-2 text-sm border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
                />
              ) : (
                <span className="text-xs text-gray-500 dark:text-slate-400 px-2 py-2 max-w-[18rem] leading-snug">
                  Local grading uses default model in server, not configurable here.
                </span>
              )}
              <button
                onClick={handleStartGrading}
                disabled={loading}
                className="px-8 py-3 bg-emerald-600 text-white rounded-xl font-medium hover:bg-emerald-700 
                           shadow-md hover:shadow-lg transition-all duration-200 flex items-center gap-2
                           disabled:opacity-50 disabled:pointer-events-none"
              >
                {loading ? (
                  <>
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Starting...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Start Grading
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Region Viewer Modal */}
      {showRegionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in overflow-auto">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-xl w-full max-w-[95vw] max-h-[90vh] flex flex-col overflow-hidden my-4 border border-gray-200/80 dark:border-slate-700">
            <div className="p-4 border-b border-gray-100 dark:border-slate-700 flex justify-between items-center bg-gray-50/80 dark:bg-slate-800/90">
              <div>
                <h3 className="text-lg font-bold text-gray-900 dark:text-slate-100">
                  {selectedDocType === 'question'
                    ? 'Crop Question Paper Region'
                    : 'Crop Student Answer Region'}
                </h3>
                <p className="text-xs text-gray-500 dark:text-slate-400">
                  Scroll and drag to crop on desired region
                </p>
                {selectedDocType === 'question' && (
                  <label className="mt-2 inline-flex items-center gap-2 text-xs text-gray-700 dark:text-slate-300">
                    <input
                      type="checkbox"
                      checked={autoCleanupEnabled}
                      onChange={(e) => setAutoCleanupEnabled(e.target.checked)}
                      className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                    />
                    Auto-clean extracted question text (Ollama)
                  </label>
                )}
              </div>
              <button 
                onClick={() => handleCloseRegionModal()}
                className="p-2 text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-200 hover:bg-gray-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden p-6 bg-gray-50 dark:bg-slate-950/80">
              {loadingRegions ? (
                <div className="flex flex-col items-center justify-center py-12 flex-1">
                   <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
                   <p className="text-sm text-gray-500 dark:text-slate-400">Loading regions...</p>
                </div>
              ) : (
                <div className="flex flex-1 min-h-0 overflow-hidden flex-col md:flex-row gap-6">
                  {/* Left: All exam pages stacked, scroll seamlessly; marked regions stay until deleted on right */}
                  <div className="w-full md:w-[45%] md:min-w-[280px] md:max-w-[50%] flex-shrink-0 min-h-0 overflow-y-auto overflow-x-hidden">
                    {pages.length > 0 && (
                      <div className="w-full min-w-0 space-y-6">
                        {loadingPageImages ? (
                          <div className="flex items-center justify-center min-h-[40vh] w-full bg-gray-100 dark:bg-slate-800 rounded-xl">
                            <div className="animate-spin rounded-full h-10 w-10 border-2 border-indigo-200 border-t-indigo-600" />
                          </div>
                        ) : (
                          pages.map((p) => {
                            const pageNum = p.page_number
                            const url = pageImageUrls[pageNum]
                            const imgRef = pageImgRefs.current[pageNum]
                            const isActiveCropPage = activePage === pageNum
                            return (
                              <div
                                key={pageNum}
                                data-page={pageNum}
                                className="relative w-full border border-gray-200 dark:border-slate-600 rounded-xl overflow-hidden bg-white dark:bg-slate-900 cursor-crosshair"
                                onMouseDown={(e) => {
                                  const wrapper = e.currentTarget
                                  const img = wrapper.querySelector('img')
                                  if (!img || !url) return
                                  const rect = img.getBoundingClientRect()
                                  const start = { x: e.clientX - rect.left, y: e.clientY - rect.top }
                                  cropImageRef.current = img
                                  setActivePage(pageNum)
                                  cropStartRef.current = start
                                  cropEndRef.current = null
                                  setIsCropping(true)
                                  setCropStart(start)
                                  setCropEnd(null)
                                }}
                              >
                                {url ? (
                                  <img
                                    ref={(el) => {
                                      if (!pageImgRefs.current) pageImgRefs.current = {}
                                      if (el) pageImgRefs.current[pageNum] = el
                                    }}
                                    src={url}
                                    alt={`Page ${pageNum}`}
                                    className="w-full h-auto max-w-full select-none block"
                                    draggable={false}
                                    onLoad={(e) => {
                                      const img = e.target
                                      setPageDimensions(prev => ({ ...prev, [pageNum]: { w: img.naturalWidth, h: img.naturalHeight } }))
                                    }}
                                  />
                                ) : (
                                  <div className="flex items-center justify-center min-h-[200px] w-full bg-gray-100 dark:bg-slate-800">
                                    <span className="text-xs text-gray-400 dark:text-slate-500">Page {pageNum}</span>
                                  </div>
                                )}
                                {/* Crop rectangle in progress (only on this page) */}
                                {isActiveCropPage && cropStart && cropEnd && (
                                  <div
                                    className="absolute border-2 border-emerald-500 bg-emerald-500/10 pointer-events-none"
                                    style={{
                                      left: Math.min(cropStart.x, cropEnd.x),
                                      top: Math.min(cropStart.y, cropEnd.y),
                                      width: Math.abs(cropEnd.x - cropStart.x),
                                      height: Math.abs(cropEnd.y - cropStart.y)
                                    }}
                                  />
                                )}
                                {/* Permanent marked regions for this page (removed only when deleted on right) */}
                                {(() => {
                                  const dims = pageDimensions[pageNum]
                                  if (!dims?.w || !dims?.h) return null
                                  const nw = dims.w
                                  const nh = dims.h
                                  return regions
                                    .filter(r => r.page_number === pageNum && r.bounding_box && r.bounding_box.width && r.bounding_box.height)
                                    .map((r) => {
                                      const b = r.bounding_box
                                      const x = b.x ?? 0
                                      const y = b.y ?? 0
                                      const w = b.width ?? 0
                                      const h = b.height ?? 0
                                      const color = regionColorMap[r.id]
                                      const borderClass = color ? color.fillBorder : 'border-emerald-500/90'
                                      const bgClass = color ? color.fillBg : 'bg-emerald-400/25'
                                      return (
                                        <div
                                          key={r.id}
                                          className={`absolute border-2 ${borderClass} ${bgClass} pointer-events-none`}
                                          style={{
                                            left: `${(x / nw) * 100}%`,
                                            top: `${(y / nh) * 100}%`,
                                            width: `${(w / nw) * 100}%`,
                                            height: `${(h / nh) * 100}%`
                                          }}
                                        >
                                          {/* Question label pill anchored near the left edge of the region */}
                                          <div className="absolute left-1 top-1">
                                            <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-white/90 dark:bg-slate-800/95 text-emerald-900/80 dark:text-emerald-300 shadow-sm">
                                              {regionColorMap[r.id]?.label || `Q${regions.findIndex(reg => reg.id === r.id) + 1}`}
                                            </span>
                                          </div>
                                        </div>
                                      )
                                    })
                                })()}
                              </div>
                            )
                          })
                        )}
                      </div>
                    )}
                  </div>

                  {/* Right: Extracted answers (independently scrollable) */}
                  <div className="flex-1 min-w-0 min-h-0 overflow-y-auto overflow-x-hidden flex flex-col">
                    <div className="sticky top-0 z-20 flex items-center gap-2 mb-3 flex-shrink-0 py-2.5 bg-gray-50/92 dark:bg-slate-900/92 backdrop-blur-md border-b border-gray-200/70 dark:border-slate-600/70 shadow-sm shadow-gray-900/[0.06] dark:shadow-black/20">
                      <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300">Extracted Text</h4>
                      {processingNewCrop && (
                        <span className="inline-flex items-center gap-1 text-xs text-indigo-600">
                          <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                          </svg>
                          Processing…
                        </span>
                      )}
                    </div>
                    {regions.length === 0 ? (
                      <div className="text-center py-12 text-gray-500 dark:text-slate-400 bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-600 border-dashed">
                        <svg className="w-12 h-12 mx-auto mb-3 text-gray-300 dark:text-slate-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <p>No regions yet. Draw a box on the page image to create one.</p>
                      </div>
                    ) : (
                      <div className="space-y-4">
                        {regions.map((region, index) => (
                          <div
                            key={region.id}
                            draggable
                            data-index={index}
                            onDragStart={(e) => {
                              if (e.target.closest('button')) {
                                e.preventDefault()
                                return
                              }
                              e.dataTransfer.setData('text/plain', String(index))
                              e.dataTransfer.effectAllowed = 'move'
                            }}
                            onDragOver={(e) => {
                              e.preventDefault()
                              e.dataTransfer.dropEffect = 'move'
                            }}
                            onDrop={(e) => {
                              e.preventDefault()
                              const from = Number(e.dataTransfer.getData('text/plain'))
                              const to = Number(e.currentTarget.dataset.index)
                              if (from === to) return
                              setRegions(prev => {
                                const next = [...prev]
                                const [removed] = next.splice(from, 1)
                                next.splice(to, 0, removed)
                                return next
                              })
                            }}
                            className="bg-white dark:bg-slate-900 rounded-xl border border-gray-200 dark:border-slate-600 p-4 shadow-sm hover:shadow-md dark:hover:shadow-slate-900/50 transition-shadow cursor-grab active:cursor-grabbing"
                          >
                            <div className="flex justify-between items-start mb-3">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-gray-400 cursor-grab active:cursor-grabbing flex-shrink-0" title="Drag to reorder">
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                  </svg>
                                </span>
                                {(() => {
                                  const badgeClass =
                                    regionColorMap[region.id]?.badge ||
                                    'bg-gray-200 dark:bg-slate-600 text-gray-800 dark:text-slate-200'
                                  // For question paper, keep using the full label (with fallback index)
                                  if (selectedDocType === 'question') {
                                    return (
                                      <span className={`text-xs font-semibold px-2 py-1 rounded-md ${badgeClass}`}>
                                        {region.question_number ||
                                          regionColorMap[region.id]?.label ||
                                          `Q${index + 1}`}
                                      </span>
                                    )
                                  }
                                  // For student answers, NEVER derive the label from index/colour map.
                                  // Only use the explicit question_number so it stays fixed when reordered.
                                  return (
                                    <span className={`text-xs font-semibold px-2 py-1 rounded-md ${badgeClass}`}>
                                      {region.question_number || 'Q ?'}
                                    </span>
                                  )
                                })()}
                                <span className="badge-draft">Page {region.page_number}</span>
                                {selectedDocType === 'question' && (
                                  <div className="flex items-center gap-1 text-xs text-gray-500">
                                    <span>Marks:</span>
                                    <input
                                      type="number"
                                      min={0}
                                      value={region.marks ?? ''}
                                      onChange={(e) => {
                                        const val = e.target.value === '' ? null : Number(e.target.value)
                                        setRegions(prev => {
                                          const next = prev.map(r =>
                                            r.id === region.id ? { ...r, marks: val } : r
                                          )
                                          return next
                                        })
                                        processingAPI
                                          .updateRegionText(region.id, { marks: val })
                                          .catch(() => {})
                                      }}
                                      className="w-14 px-1 py-0.5 border border-gray-200 rounded-md text-xs focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                                    />
                                  </div>
                                )}
                                {selectedDocType === 'question' && regionCleanupMeta[region.id]?.processed && (
                                  <span className="text-[11px] px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 border border-emerald-200">
                                    Cleaned ({regionCleanupMeta[region.id]?.provider || 'ollama'})
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-1 flex-shrink-0">
                                <button
                                  onClick={() => handleRunOcr(region.id)}
                                  disabled={runningOcrFor === region.id}
                                  className="text-xs font-medium px-2 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg transition-colors flex items-center gap-1 disabled:opacity-50"
                                  title="Re-run OCR"
                                >
                                  {runningOcrFor === region.id ? (
                                    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                  ) : (
                                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                                    </svg>
                                  )}
                                </button>
                                <button
                                  onClick={() => handleDeleteRegion(region.id)}
                                  className="text-xs font-medium px-2 py-1.5 bg-red-50 text-red-600 hover:bg-red-100 rounded-lg transition-colors flex items-center gap-1"
                                  title="Delete region"
                                >
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V7a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                            <div className="bg-gray-50 dark:bg-slate-800/50 rounded-lg border border-gray-200 dark:border-slate-600">
                              {selectedDocType === 'question' && (() => {
                                const label = region.question_number || regionColorMap[region.id]?.label || `Q${index + 1}`
                                const { main, part, sub } = parseQuestionComponents(label)

                                // Enforce non-decreasing main question number based on earlier regions
                                const previous = regions.slice(0, index)
                                const maxMainSoFar = previous.reduce((max, r) => {
                                  const lbl = r.question_number || regionColorMap[r.id]?.label || `Q${regions.findIndex(reg => reg.id === r.id) + 1}`
                                  const { main: mPrev } = parseQuestionComponents(lbl)
                                  return mPrev && mPrev > max ? mPrev : max
                                }, 0)

                                const effectiveMain = main || Math.max(1, maxMainSoFar || 1)

                                // For parts and subparts, enforce non-decreasing within the same main question
                                const partOrder = (v) => {
                                  if (!v || v === '-') return 0
                                  const idx = PART_OPTIONS.indexOf(v)
                                  return idx === -1 ? 0 : idx
                                }
                                const subOrder = (v) => {
                                  if (!v || v === '-') return 0
                                  const idx = SUBPART_OPTIONS.indexOf(v)
                                  return idx === -1 ? 0 : idx
                                }

                                let maxPartSoFar = 0
                                let maxSubSoFar = 0
                                const usedSubsForCurrentPart = new Set()
                                previous.forEach((r) => {
                                  const lbl = r.question_number || regionColorMap[r.id]?.label || `Q${regions.findIndex(reg => reg.id === r.id) + 1}`
                                  const { main: mPrev, part: pPrev, sub: sPrev } = parseQuestionComponents(lbl)
                                  if (mPrev === effectiveMain) {
                                    maxPartSoFar = Math.max(maxPartSoFar, partOrder(pPrev))
                                    if ((pPrev || '-') === (part || '-')) {
                                      const so = subOrder(sPrev)
                                      maxSubSoFar = Math.max(maxSubSoFar, so)
                                      if (sPrev) usedSubsForCurrentPart.add(sPrev)
                                    }
                                  }
                                })

                                const handleChange = (nextMain, nextPart, nextSub) => {
                                  const oldLabel = (region.question_number || '').trim()
                                  const finalLabel = formatQuestionLabel(nextMain, nextPart, nextSub)
                                  setRegions(prev =>
                                    prev.map(r =>
                                      r.id === region.id ? { ...r, question_number: finalLabel } : r
                                    )
                                  )
                                  processingAPI
                                    .updateRegionText(region.id, {
                                      question_number: finalLabel,
                                      old_question_number: oldLabel,
                                      sync_student_regions: true
                                    })
                                    .catch(() => {})
                                }

                                return (
                                  <div className="px-3 pt-2 pb-1 flex flex-wrap items-center gap-2">
                                    <span className="text-[11px] font-medium text-gray-600">
                                      Question number
                                    </span>
                                    {/* Main question (Q1..Q6). When main changes, reset part+sub to smallest allowed */}
                                    <select
                                      value={effectiveMain}
                                      onChange={(e) => {
                                        const nextMain = parseInt(e.target.value, 10)
                                        // Recompute constraints for this main question based on previous regions
                                        const prevForMain = previous.filter((r) => {
                                          const lbl = r.question_number || regionColorMap[r.id]?.label || `Q${regions.findIndex(reg => reg.id === r.id) + 1}`
                                          const { main: mPrev } = parseQuestionComponents(lbl)
                                          return mPrev === nextMain
                                        })

                                        let maxPartForMain = 0
                                        const partOrderFor = (v) => {
                                          if (!v || v === '-') return 0
                                          const idx = PART_OPTIONS.indexOf(v)
                                          return idx === -1 ? 0 : idx
                                        }
                                        prevForMain.forEach((r) => {
                                          const lbl = r.question_number || regionColorMap[r.id]?.label || ''
                                          const { part: pPrev } = parseQuestionComponents(lbl)
                                          maxPartForMain = Math.max(maxPartForMain, partOrderFor(pPrev))
                                        })

                                        // Pick smallest allowed part for this main
                                        let nextPart = 'a'
                                        for (const pOpt of PART_OPTIONS) {
                                          if (pOpt === '-') continue
                                          const disabled = partOrderFor(pOpt) < maxPartForMain
                                          if (!disabled) {
                                            nextPart = pOpt
                                            break
                                          }
                                        }

                                        // For that (main, part), find smallest allowed sub (respecting previous uses)
                                        const prevForMainPart = prevForMain.filter((r) => {
                                          const lbl = r.question_number || regionColorMap[r.id]?.label || ''
                                          const { part: pPrev } = parseQuestionComponents(lbl)
                                          return (pPrev || '-') === nextPart
                                        })
                                        const subOrderFor = (v) => {
                                          if (!v || v === '-') return 0
                                          const idx = SUBPART_OPTIONS.indexOf(v)
                                          return idx === -1 ? 0 : idx
                                        }
                                        let maxSubForMainPart = 0
                                        const usedSubs = new Set()
                                        prevForMainPart.forEach((r) => {
                                          const lbl = r.question_number || regionColorMap[r.id]?.label || ''
                                          const { sub: sPrev } = parseQuestionComponents(lbl)
                                          const so = subOrderFor(sPrev)
                                          maxSubForMainPart = Math.max(maxSubForMainPart, so)
                                          if (sPrev) usedSubs.add(sPrev)
                                        })
                                        let nextSub = '-'
                                        for (const sOpt of SUBPART_OPTIONS) {
                                          const disabled =
                                            (subOrderFor(sOpt) < maxSubForMainPart && sOpt !== '-') ||
                                            (usedSubs.has(sOpt) && sOpt !== '-')
                                          if (!disabled) {
                                            nextSub = sOpt
                                            break
                                          }
                                        }

                                        handleChange(nextMain, nextPart, nextSub)
                                      }}
                                      className="px-1.5 py-1 text-xs border border-gray-200 dark:border-slate-600 rounded-md bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                                    >
                                      {MAIN_QUESTION_OPTIONS.map((qNo) => {
                                        const disabled = qNo < maxMainSoFar
                                        return (
                                          <option
                                            key={qNo}
                                            value={qNo}
                                            disabled={disabled}
                                            className={disabled ? 'text-gray-400' : undefined}
                                          >
                                            Q{qNo}
                                          </option>
                                        )
                                      })}
                                    </select>
                                    {/* Part (a..j). When part changes, reset sub to smallest allowed for that part */}
                                    <select
                                      value={part || '-'}
                                      onChange={(e) => {
                                        const nextPart = e.target.value

                                        // For this (main, nextPart), compute smallest allowed sub
                                        const subOrderFor = (v) => {
                                          if (!v || v === '-') return 0
                                          const idx = SUBPART_OPTIONS.indexOf(v)
                                          return idx === -1 ? 0 : idx
                                        }

                                        let maxSubForPart = 0
                                        const usedSubs = new Set()
                                        previous.forEach((r) => {
                                          const lbl = r.question_number || regionColorMap[r.id]?.label || `Q${regions.findIndex(reg => reg.id === r.id) + 1}`
                                          const { main: mPrev, part: pPrev, sub: sPrev } = parseQuestionComponents(lbl)
                                          if (mPrev === effectiveMain && (pPrev || '-') === nextPart) {
                                            const so = subOrderFor(sPrev)
                                            maxSubForPart = Math.max(maxSubForPart, so)
                                            if (sPrev) usedSubs.add(sPrev)
                                          }
                                        })

                                        let nextSub = '-'
                                        for (const sOpt of SUBPART_OPTIONS) {
                                          const disabled =
                                            (subOrderFor(sOpt) < maxSubForPart && sOpt !== '-') ||
                                            (usedSubs.has(sOpt) && sOpt !== '-')
                                          if (!disabled) {
                                            nextSub = sOpt
                                            break
                                          }
                                        }

                                        handleChange(effectiveMain, nextPart, nextSub)
                                      }}
                                      className="px-1.5 py-1 text-xs border border-gray-200 dark:border-slate-600 rounded-md bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                                    >
                                      {PART_OPTIONS.map((pOpt) => {
                                        const disabled = partOrder(pOpt) < maxPartSoFar && pOpt !== '-'
                                        return (
                                          <option
                                            key={pOpt}
                                            value={pOpt}
                                            disabled={disabled}
                                            className={disabled ? 'text-gray-400' : undefined}
                                          >
                                            {pOpt}
                                          </option>
                                        )
                                      })}
                                    </select>
                                    {/* Subpart (i..xiii) – cannot reuse same sub for same main+part */}
                                    <select
                                      value={sub || '-'}
                                      onChange={(e) => {
                                        const nextSub = e.target.value
                                        handleChange(effectiveMain, part || '-', nextSub)
                                      }}
                                      className="px-1.5 py-1 text-xs border border-gray-200 dark:border-slate-600 rounded-md bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-1 focus:ring-indigo-500 focus:border-indigo-500"
                                    >
                                      {SUBPART_OPTIONS.map((sOpt) => {
                                        const disabled =
                                          (subOrder(sOpt) < maxSubSoFar && sOpt !== '-') ||
                                          (usedSubsForCurrentPart.has(sOpt) && sOpt !== (sub || '-'))
                                        return (
                                          <option
                                            key={sOpt}
                                            value={sOpt}
                                            disabled={disabled}
                                            className={disabled ? 'text-gray-400' : undefined}
                                          >
                                            {sOpt}
                                          </option>
                                        )
                                      })}
                                    </select>
                                  </div>
                                )
                              })()}
                              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 px-3 pt-2">
                                Extracted text (editable)
                              </label>
                              <textarea
                                value={region.raw_text ?? ''}
                                onChange={(e) => {
                                  const value = e.target.value
                                  setRegions(prev =>
                                    prev.map(r =>
                                      r.id === region.id
                                        ? { ...r, raw_text: value }
                                        : r
                                    )
                                  )
                                }}
                                onFocus={() => { editFocusRef.current = { id: region.id, value: region.raw_text ?? '' } }}
                                onBlur={(e) => {
                                  const value = e.target.value
                                  if (editFocusRef.current.id === region.id && value !== editFocusRef.current.value) {
                                    handleUpdateRegionText(region.id, value)
                                  }
                                }}
                                className="w-full min-h-[80px] px-3 pb-3 pt-1 text-sm text-gray-800 dark:text-slate-200 font-mono whitespace-pre-wrap border-0 bg-transparent focus:ring-2 focus:ring-indigo-500/30 focus:outline-none rounded-b-lg resize-y"
                                placeholder="No text extracted. Use Re-run OCR or type here."
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
            
            <div className="p-4 border-t border-gray-100 dark:border-slate-700 bg-white dark:bg-slate-900 flex items-center justify-end gap-4">
              {selectedDocType === 'question' && (
                <span className="text-sm font-medium text-gray-700 dark:text-slate-300">
                  Total marks:{' '}
                  {(regions || []).reduce(
                    (sum, r) => sum + (Number.isFinite(r.marks) ? Number(r.marks) : 0),
                    0
                  )}
                </span>
              )}
              <button
                onClick={() => handleCloseRegionModal()}
                className="btn-primary"
              >
                Save & Close
              </button>
            </div>
          </div>
        </div>
      )}

      {captureDialog.open && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-2xl border border-gray-200 dark:border-slate-700 p-5 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-semibold text-gray-900 dark:text-slate-100">Scan with your phone</h3>
                <p className="text-xs text-gray-500 dark:text-slate-400">
                  {captureDialog.docType === 'question_paper' ? 'Question Paper' : 'Student Answer'}
                </p>
              </div>
              <button
                type="button"
                onClick={closeCaptureDialog}
                className="text-gray-400 hover:text-gray-700 dark:hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            {captureDialog.loading ? (
              <div className="text-sm text-gray-500 dark:text-slate-400">Preparing capture session...</div>
            ) : (
              <>
                {captureDialog.url ? (
                  <div className="flex flex-col items-center gap-3">
                    <img
                      src={`https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(captureDialog.url)}`}
                      alt="Capture session QR code"
                      className="w-56 h-56 rounded-lg border border-gray-200 dark:border-slate-700"
                    />
                    <a
                      href={captureDialog.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-indigo-600 hover:underline break-all text-center"
                    >
                      {captureDialog.url}
                    </a>
                    <p className="text-xs text-gray-500 dark:text-slate-400 text-center">
                      Keep this dialog open. It auto-refreshes when phone upload is done.
                    </p>
                  </div>
                ) : (
                  <div className="text-sm text-red-600">Failed to create capture link.</div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default GradePaper
