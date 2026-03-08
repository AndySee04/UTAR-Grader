import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { examsAPI, documentsAPI, processingAPI, markingGuideAPI, gradingAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

const STEPS = [
  { label: 'Upload', icon: '📤' },
  { label: 'Process', icon: '⚙️' },
  { label: 'Marking Guide', icon: '📋' },
  { label: 'Grade', icon: '✅' }
]

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
  const [dragActive, setDragActive] = useState(null)
  
  // OCR Region View State
  const [selectedDocId, setSelectedDocId] = useState(null)
  const [regions, setRegions] = useState([])
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

  // Region count per document (synced with backend); cropped = count > 0
  const [regionCountByDocId, setRegionCountByDocId] = useState({})

  const croppedDocs = useMemo(
    () => new Set(Object.entries(regionCountByDocId).filter(([, c]) => c > 0).map(([id]) => id)),
    [regionCountByDocId]
  )

  const allStudentsCropped =
    uploadedDocs.students &&
    uploadedDocs.students.length > 0 &&
    uploadedDocs.students.every((doc) => (regionCountByDocId[doc.id] ?? 0) > 0)

  const studentDocs = uploadedDocs.students || []

  const toast = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  // Load existing exam when opened from My Exams, or reset when opening "New Exam" (no state)
  useEffect(() => {
    const stateExamId = location.state?.examId
    const stateExamName = location.state?.examName

    if (!stateExamId) {
      setExamId(null)
      setExamName('')
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
        const question = Array.isArray(qList.data) ? qList.data[0] : null
        const scheme = Array.isArray(sList.data) ? sList.data[0] : null
        const students = Array.isArray(stList.data) ? stList.data : []
        setUploadedDocs({ question, scheme, students })
        setMarkingGuide(guideRes?.data ?? [])

        if ((guideRes?.data?.length ?? 0) > 0) {
          setStep(3)
        } else if (question && scheme && students.length > 0) {
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
  }, [location.state?.examId])

  // Sync region counts from backend when we have student documents (step 1)
  useEffect(() => {
    if (!examId || !studentDocs.length) return
    let cancelled = false
    const fetchCounts = async () => {
      const counts = {}
      await Promise.all(
        studentDocs.map(async (doc) => {
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
  }, [examId, studentDocs.length])

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
      const payload = {
        page_number: activePage,
        x: Math.round(x1),
        y: Math.round(y1),
        width: w,
        height: h,
        region_type: 'student_answer'
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
        .then(({ region, raw_text }) => {
          setRegions(prev => [...prev, { ...region, raw_text }])
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
  }, [isCropping, selectedDocId, activePage])

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

  const handleDrop = useCallback((e, setter, multiple = false) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(null)
    const files = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf')
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

  // Step 1: Upload
  const handleUpload = async () => {
    if (!examName.trim()) {
      setError('Please enter an exam name')
      return
    }
    if (!questionPaper || !answerScheme || studentAnswers.length === 0) {
      setError('Please upload all required documents')
      return
    }

    setLoading(true)
    setError('')

    try {
      const examRes = await examsAPI.create({ name: examName })
      const newExamId = examRes.data.id
      setExamId(newExamId)

      const qRes = await documentsAPI.upload(newExamId, questionPaper, 'question_paper')
      const sRes = await documentsAPI.upload(newExamId, answerScheme, 'answer_scheme')
      const stRes = await documentsAPI.uploadMultiple(newExamId, studentAnswers, 'student_answer')

      setUploadedDocs({
        question: qRes.data,
        scheme: sRes.data,
        students: stRes.data
      })

      toast.success('Documents uploaded successfully!')
      setStep(1)
    } catch (err) {
      setError(err.response?.data?.detail || 'Upload failed')
    } finally {
      setLoading(false)
    }
  }

  // Step 2: Process
  const handleProcess = async () => {
    setProcessing(true)
    setError('')
    setProcessStatus('Initializing OCR engine...')

    try {
      await processingAPI.processExam(examId)

      // Poll progress
      const stages = [
        'Detecting text regions...',
        'Running OCR on detected regions...',
        'Cleaning up extracted text...',
        'Finalizing document processing...'
      ]
      for (let i = 0; i < stages.length; i++) {
        setProcessStatus(stages[i])
        await new Promise(resolve => setTimeout(resolve, 2000))
      }

      toast.success('Documents processed successfully!')
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail || 'Processing failed')
    } finally {
      setProcessing(false)
      setProcessStatus('')
    }
  }

  // --- Regions View ---
  const handleViewRegions = async (docId) => {
    setSelectedDocId(docId)
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
        setRegions(list)
      } catch (err) {
        if (err?.response?.status === 404) {
          setRegions([])
        } else {
          throw err
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

  const handleRunOcr = async (regionId) => {
    setRunningOcrFor(regionId)
    try {
      const res = await processingAPI.runOCR(regionId)
      setRegions(prev => prev.map(r =>
        r.id === regionId
          ? { ...r, raw_text: res.data?.raw_text ?? res.data?.text ?? r.raw_text }
          : r
      ))
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
      await processingAPI.updateRegionText(regionId, rawText)
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
          processingAPI.updateRegionText(r.id, r.raw_text ?? '').catch(() => {})
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

    try {
      const res = await markingGuideAPI.generate(examId)
      setMarkingGuide(res.data.marking_guide || [])
      toast.success('Marking guide generated!')
      setStep(3)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to generate marking guide')
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
        question_type: 'short_answer',
        max_marks: 1,
        expected_answer: ''
      })
      setMarkingGuide([...markingGuide, res.data])
      toast.info('Question added')
    } catch (err) {
      toast.error('Failed to add question')
    }
  }

  const handleDeleteQuestion = async (index) => {
    const guide = markingGuide[index]
    try {
      await markingGuideAPI.deleteQuestion(guide.id)
      setMarkingGuide(markingGuide.filter((_, i) => i !== index))
      toast.info('Question removed')
    } catch (err) {
      toast.error('Failed to delete question')
    }
  }

  // Step 4: Start Grading
  const handleStartGrading = async () => {
    setLoading(true)
    setError('')

    try {
      await gradingAPI.start(examId)
      toast.success('Grading started! Check the Exam List for progress.')
      navigate('/exams')
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to start grading')
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
          <h3 className="font-semibold text-gray-700">{label}</h3>
          {file ? (
            <span className="text-sm text-emerald-600 font-medium">
              {typeof file === 'object' && file.name ? file.name : `${file} files selected`}
            </span>
          ) : (
            <span className="text-sm text-gray-400">{subtitle}</span>
          )}
        </div>
      </label>
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Grade Paper</h1>
        <p className="text-sm text-gray-500 mt-1">Upload, process, and grade exam papers with AI</p>
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
                  'bg-gray-100 text-gray-400'
                }`}>
                  {i < step ? (
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : (
                    <span>{s.icon}</span>
                  )}
                </div>
                <span className={`text-sm font-medium hidden sm:block ${
                  i <= step ? 'text-gray-900' : 'text-gray-400'
                }`}>{s.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-4 rounded-full transition-colors ${
                  i < step ? 'bg-emerald-400' : 'bg-gray-200'
                }`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl text-sm animate-fade-in">
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
            <label className="block text-sm font-medium text-gray-700 mb-1.5">Exam Name</label>
            <input
              type="text"
              value={examName}
              onChange={(e) => setExamName(e.target.value)}
              className="input-field"
              placeholder="e.g., Mid-Term Exam 2024"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <FileDropZone
              id="question-paper"
              label="Question Paper"
              subtitle="Drop PDF or click to browse"
              file={questionPaper}
              onFileChange={(e) => setQuestionPaper(e.target.files[0])}
              onDrop={(e) => handleDrop(e, setQuestionPaper)}
              zone="question"
            />
            <FileDropZone
              id="answer-scheme"
              label="Answer Scheme"
              subtitle="Drop PDF or click to browse"
              file={answerScheme}
              onFileChange={(e) => setAnswerScheme(e.target.files[0])}
              onDrop={(e) => handleDrop(e, setAnswerScheme)}
              zone="scheme"
            />
          </div>

          <div>
            <FileDropZone
              id="student-answers"
              label="Student Answer Sheets"
              subtitle="Drop multiple PDFs or click to browse"
              file={studentAnswers.length > 0 ? `${studentAnswers.length}` : null}
              onFileChange={(e) => setStudentAnswers(prev => [...prev, ...Array.from(e.target.files)])}
              onDrop={(e) => handleDrop(e, setStudentAnswers, true)}
              zone="students"
              multiple
            />
            {studentAnswers.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2">
                {studentAnswers.map((file, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 rounded-lg text-sm">
                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                    </svg>
                    <span className="text-gray-600 truncate max-w-[150px]">{file.name}</span>
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
            <h2 className="text-lg font-semibold text-gray-900">Process Documents</h2>
            <p className="text-sm text-gray-500 mt-1">
              First, manually crop each student answer region. Then the system will detect text regions on the question paper and answer scheme and extract text using OCR.
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="bg-indigo-50/50 rounded-xl p-4 border border-indigo-100">
              <p className="text-xs font-medium text-indigo-500 uppercase tracking-wide">Question Paper</p>
              <p className="text-2xl font-bold text-indigo-700 mt-1">{uploadedDocs.question?.page_count || 0}</p>
              <p className="text-xs text-indigo-400">pages</p>
            </div>
            <div className="bg-purple-50/50 rounded-xl p-4 border border-purple-100">
              <p className="text-xs font-medium text-purple-500 uppercase tracking-wide">Answer Scheme</p>
              <p className="text-2xl font-bold text-purple-700 mt-1">{uploadedDocs.scheme?.page_count || 0}</p>
              <p className="text-xs text-purple-400">pages</p>
            </div>
            <div className="bg-emerald-50/50 rounded-xl p-4 border border-emerald-100">
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
              <p className="text-sm font-medium text-gray-600">{processStatus}</p>
              <div className="w-full max-w-xs progress-bar">
                <div className="progress-bar-fill" style={{ width: '60%' }} />
              </div>
            </div>
          )}

          {!processing && studentDocs.length > 0 && (
            <div className="mt-6 border-t border-gray-100 pt-6">
              <h3 className="text-sm font-semibold text-gray-900 mb-1">Crop Student Answer Regions</h3>
              <p className="text-xs text-gray-500 mb-2">
                The website will guide you through each student answer. Click a student to open their pages, then drag boxes over each answer region. Do this for every student before starting processing.
              </p>
              <p className="text-xs font-medium text-gray-600 mb-4">
                Progress: {Array.from(croppedDocs).length} / {studentDocs.length} students cropped
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {studentDocs
                  .slice()
                  .sort((a, b) => {
                    const aDone = croppedDocs.has(a.id)
                    const bDone = croppedDocs.has(b.id)
                    if (aDone === bDone) return (a.student_name || '').localeCompare(b.student_name || '')
                    return aDone ? 1 : -1
                  })
                  .map((doc) => (
                    <button
                      key={doc.id}
                      onClick={() => handleViewRegions(doc.id)}
                      className="text-left p-3 rounded-xl border border-gray-200 hover:border-indigo-400 hover:bg-indigo-50/30 transition-all group flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2 overflow-hidden">
                        <svg className="w-5 h-5 text-gray-400 group-hover:text-indigo-500 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        <div className="flex flex-col">
                          <span className="text-sm font-medium text-gray-700 truncate">
                            {doc.student_name || 'Student Document'}
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
                      <svg className="w-4 h-4 text-gray-300 group-hover:text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </button>
                  ))}
              </div>
            </div>
          )}

          <div className="flex gap-3">
            <button
              onClick={() => setStep(0)}
              className="btn-secondary"
            >
              <svg className="w-4 h-4 inline mr-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
              Back
            </button>
            <button
              onClick={handleProcess}
              disabled={processing || !allStudentsCropped}
              className="flex-1 btn-primary py-3 flex justify-center items-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {processing ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing...
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
          {!processing && studentDocs.length > 0 && !allStudentsCropped && (
            <p className="text-xs text-amber-600 mt-2">
              Please crop at least one answer region for each student document before starting processing.
            </p>
          )}
        </div>
      )}

      {/* Step 3: Generate Marking Guide */}
      {step === 2 && (
        <div className="card p-6 space-y-6 animate-fade-in">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Generate Marking Guide</h2>
            <p className="text-sm text-gray-500 mt-1">
              The AI will analyze the question paper and answer scheme to generate a marking guide template.
            </p>
          </div>

          <div className="bg-indigo-50/30 border border-indigo-100 rounded-xl p-4 flex items-start gap-3">
            <svg className="w-5 h-5 text-indigo-500 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-sm text-indigo-700">
              The AI will attempt to identify questions and expected answers automatically. You can edit the results in the next step.
            </p>
          </div>

          <div className="flex gap-3">
            <button onClick={() => setStep(1)} className="btn-secondary">
              Back
            </button>
            <button
              onClick={handleGenerateGuide}
              disabled={loading}
              className="flex-1 btn-primary py-3 flex justify-center items-center gap-2"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Generating...
                </>
              ) : (
                <>
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  Generate Marking Guide
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* Step 3b: Edit Marking Guide */}
      {step === 3 && (
        <div className="card p-6 space-y-6 animate-fade-in">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Review Marking Guide</h2>
              <p className="text-sm text-gray-500 mt-1">Edit questions, types, and marks as needed.</p>
            </div>
            <button onClick={handleAddQuestion} className="btn-secondary text-sm flex items-center gap-1">
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Question
            </button>
          </div>

          <div className="overflow-x-auto rounded-xl border border-gray-100">
            <table className="w-full">
              <thead>
                <tr className="table-header">
                  <th className="px-4 py-3 text-left">Q.No</th>
                  <th className="px-4 py-3 text-left">Question</th>
                  <th className="px-4 py-3 text-left">Type</th>
                  <th className="px-4 py-3 text-left">Marks</th>
                  <th className="px-4 py-3 text-left w-12"></th>
                </tr>
              </thead>
              <tbody>
                {markingGuide.map((q, i) => (
                  <tr key={q.id} className="table-row">
                    <td className="px-4 py-3">
                      <input
                        value={q.question_number}
                        onChange={(e) => updateGuideQuestion(i, 'question_number', e.target.value)}
                        className="w-16 px-2 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <input
                        value={q.question_text || ''}
                        onChange={(e) => updateGuideQuestion(i, 'question_text', e.target.value)}
                        className="w-full px-2 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
                        placeholder="Enter question text..."
                      />
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={q.question_type || 'short_answer'}
                        onChange={(e) => updateGuideQuestion(i, 'question_type', e.target.value)}
                        className="px-2 py-1.5 border border-gray-200 rounded-lg text-sm bg-white focus:ring-indigo-500 focus:border-indigo-500"
                      >
                        <option value="short_answer">Short Answer</option>
                        <option value="essay">Essay</option>
                        <option value="mcq">MCQ</option>
                        <option value="calculation">Calculation</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        value={q.max_marks || 0}
                        onChange={(e) => updateGuideQuestion(i, 'max_marks', parseFloat(e.target.value))}
                        className="w-20 px-2 py-1.5 border border-gray-200 rounded-lg text-sm focus:ring-indigo-500 focus:border-indigo-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleDeleteQuestion(i)}
                        className="p-1 text-gray-400 hover:text-red-500 rounded transition-colors"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-between items-center pt-2">
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-500">
                {markingGuide.length} questions
              </span>
              <span className="text-sm font-semibold text-gray-700 bg-gray-100 px-3 py-1 rounded-full">
                Total: {markingGuide.reduce((sum, q) => sum + (q.max_marks || 0), 0)} marks
              </span>
            </div>
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
      )}

      {/* Region Viewer Modal */}
      {showRegionModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4 animate-fade-in overflow-auto">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-[95vw] max-h-[90vh] flex flex-col overflow-hidden my-4">
            <div className="p-4 border-b border-gray-100 flex justify-between items-center bg-gray-50/80">
              <div>
                <h3 className="text-lg font-bold text-gray-900">Detected Regions</h3>
                <p className="text-xs text-gray-500">
                  Draw boxes on the page image to capture student answers, then review OCR text per region.
                </p>
              </div>
              <button 
                onClick={() => handleCloseRegionModal()}
                className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            
            <div className="flex-1 min-h-0 flex flex-col overflow-hidden p-6 bg-gray-50">
              {loadingRegions ? (
                <div className="flex flex-col items-center justify-center py-12 flex-1">
                   <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-indigo-600 mb-4"></div>
                   <p className="text-sm text-gray-500">Loading regions...</p>
                </div>
              ) : (
                <div className="flex flex-1 min-h-0 overflow-hidden flex-col md:flex-row gap-6">
                  {/* Left: All exam pages stacked, scroll seamlessly; marked regions stay until deleted on right */}
                  <div className="w-full md:w-[45%] md:min-w-[280px] md:max-w-[50%] flex-shrink-0 min-h-0 overflow-y-auto overflow-x-hidden">
                    {pages.length > 0 && (
                      <div className="w-full min-w-0 space-y-6">
                        <h4 className="text-sm font-semibold text-gray-700 mb-2">Exam pages — scroll and drag to crop on any page</h4>
                        {loadingPageImages ? (
                          <div className="flex items-center justify-center min-h-[40vh] w-full bg-gray-100 rounded-xl">
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
                                className="relative w-full border border-gray-200 rounded-xl overflow-hidden bg-white cursor-crosshair"
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
                                  <div className="flex items-center justify-center min-h-[200px] w-full bg-gray-100">
                                    <span className="text-xs text-gray-400">Page {pageNum}</span>
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
                                      return (
                                      <div
                                        key={r.id}
                                        className="absolute border-2 border-emerald-500/90 bg-emerald-400/25 pointer-events-none flex items-center justify-center"
                                        style={{
                                          left: `${(x / nw) * 100}%`,
                                          top: `${(y / nh) * 100}%`,
                                          width: `${(w / nw) * 100}%`,
                                          height: `${(h / nh) * 100}%`
                                        }}
                                      >
                                        <span className="text-[10px] font-bold text-emerald-800/80 drop-shadow-sm">
                                          Q{regions.findIndex(reg => reg.id === r.id) + 1}
                                        </span>
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
                    <div className="flex items-center gap-2 mb-3 flex-shrink-0">
                      <h4 className="text-sm font-semibold text-gray-700">Extracted answer</h4>
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
                      <div className="text-center py-12 text-gray-500 bg-white rounded-xl border border-gray-200 border-dashed">
                        <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                            className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm hover:shadow-md transition-shadow cursor-grab active:cursor-grabbing"
                          >
                            <div className="flex justify-between items-start mb-3">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-gray-400 cursor-grab active:cursor-grabbing flex-shrink-0" title="Drag to reorder">
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
                                  </svg>
                                </span>
                                <span className="text-xs font-semibold px-2 py-1 rounded-md bg-gray-200 text-gray-800">
                                  Q{index + 1}
                                </span>
                                <span className="badge-draft">Page {region.page_number}</span>
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
                            <div className="bg-gray-50 rounded-lg border border-gray-200">
                              <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1 px-3 pt-2">
                                Extracted answer (editable)
                              </label>
                              <textarea
                                value={region.raw_text ?? ''}
                                onChange={(e) => {
                                  const value = e.target.value
                                  setRegions(prev => prev.map(r => r.id === region.id ? { ...r, raw_text: value } : r))
                                }}
                                onFocus={() => { editFocusRef.current = { id: region.id, value: region.raw_text ?? '' } }}
                                onBlur={(e) => {
                                  const value = e.target.value
                                  if (editFocusRef.current.id === region.id && value !== editFocusRef.current.value) {
                                    handleUpdateRegionText(region.id, value)
                                  }
                                }}
                                className="w-full min-h-[80px] px-3 pb-3 pt-1 text-sm text-gray-800 font-mono whitespace-pre-wrap border-0 bg-transparent focus:ring-2 focus:ring-indigo-500/30 focus:outline-none rounded-b-lg resize-y"
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
            
            <div className="p-4 border-t border-gray-100 bg-white flex justify-end">
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
    </div>
  )
}

export default GradePaper
