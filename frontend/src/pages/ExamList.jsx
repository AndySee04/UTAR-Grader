import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { examsAPI, reportsAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

/** One shared box model for row actions (fixed height; all native buttons so UA styles match). */
const examRowActionClass =
  'inline-flex h-9 shrink-0 items-center justify-center border px-3 text-sm font-medium leading-none transition-colors box-border rounded-lg m-0 appearance-none'

function ExamList() {
  const [exams, setExams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [sortBy, setSortBy] = useState('date_desc')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [editingExamId, setEditingExamId] = useState(null)
  const [editingExamName, setEditingExamName] = useState('')
  const [renaming, setRenaming] = useState(false)
  const toast = useToast()
  const navigate = useNavigate()

  const openExam = (exam) => {
    // For completed exams, clicking the row should open the results view.
    // For all other statuses, open the grading workflow.
    if (exam.status === 'completed') {
      navigate(`/exams/${exam.id}/results`)
    } else {
      navigate('/grade', { state: { examId: exam.id, examName: exam.name } })
    }
  }

  useEffect(() => {
    loadExams()
    const interval = setInterval(loadExams, 10000)
    return () => clearInterval(interval)
  }, [])

  const loadExams = async () => {
    try {
      const res = await examsAPI.list()
      setExams(res.data)
    } catch (err) {
      setError('Failed to load exams')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (id) => {
    setDeleting(true)
    try {
      await examsAPI.delete(id)
      setExams(exams.filter(e => e.id !== id))
      setDeleteTarget(null)
      toast.success('Exam deleted')
    } catch (err) {
      toast.error('Failed to delete exam')
    } finally {
      setDeleting(false)
    }
  }

  const startRename = (exam) => {
    setEditingExamId(exam.id)
    setEditingExamName(exam.name || '')
  }

  const cancelRename = () => {
    setEditingExamId(null)
    setEditingExamName('')
  }

  const saveRename = async (exam) => {
    const nextName = editingExamName.trim()
    if (!nextName) {
      toast.error('Exam name cannot be empty')
      return
    }
    if (nextName === (exam.name || '').trim()) {
      cancelRename()
      return
    }
    setRenaming(true)
    try {
      const res = await examsAPI.update(exam.id, { name: nextName })
      setExams((prev) => prev.map((e) => (e.id === exam.id ? { ...e, name: res.data?.name || nextName } : e)))
      toast.success('Exam name updated')
      cancelRename()
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to rename exam')
    } finally {
      setRenaming(false)
    }
  }

  const downloadExcel = async (examId, examName) => {
    try {
      toast.info('Preparing Excel download...')
      const res = await reportsAPI.downloadExcel(examId)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `${examName}_grades.xlsx`
      link.click()
      toast.success('Download started')
    } catch (err) {
      toast.error('Failed to download report')
    }
  }

  const downloadAllPDFs = async (examId, examName) => {
    try {
      toast.info('Preparing PDF download...')
      const res = await reportsAPI.downloadAllPDFs(examId)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `${examName}_all_reports.zip`
      link.click()
      toast.success('Download started')
    } catch (err) {
      toast.error('Failed to download reports')
    }
  }

  const getStatusBadge = (status) => {
    const config = {
      draft: { class: 'badge-draft', label: 'Draft' },
      processing: { class: 'badge-processing', label: 'Processing' },
      grading: { class: 'badge-grading', label: 'Grading' },
      completed: { class: 'badge-completed', label: 'Completed' }
    }
    const c = config[status] || config.draft
    return <span className={c.class}>{c.label}</span>
  }

  const normalizedQuery = searchTerm.trim().toLowerCase()
  const visibleExams = exams
    .filter((exam) => {
      if (!normalizedQuery) return true
      const name = (exam.name || '').toLowerCase()
      return name.includes(normalizedQuery)
    })
    .sort((a, b) => {
      if (sortBy === 'name_asc') {
        return (a.name || '').localeCompare(b.name || '')
      }
      if (sortBy === 'name_desc') {
        return (b.name || '').localeCompare(a.name || '')
      }
      if (sortBy === 'date_asc') {
        return new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
      }
      // default: date_desc
      return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
    })

  if (loading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="card p-6">
            <div className="flex justify-between">
              <div className="space-y-3 flex-1">
                <div className="skeleton h-5 w-48" />
                <div className="skeleton h-4 w-32" />
              </div>
              <div className="skeleton h-8 w-24" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-slate-100">My Exams</h1>
          <p className="text-sm text-gray-500 dark:text-slate-400 mt-1">{exams.length} exam{exams.length !== 1 ? 's' : ''} total</p>
        </div>
        <Link to="/grade" className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Exam
        </Link>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
          <div className="flex-1">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search by exam name..."
              className="w-full px-3 py-2 border border-gray-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 placeholder:text-gray-400 dark:placeholder:text-slate-500 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <div className="sm:w-64">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 dark:border-slate-600 rounded-lg text-sm bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-indigo-500 focus:border-indigo-500"
            >
              <option value="date_desc">Sort: Newest first</option>
              <option value="date_asc">Sort: Oldest first</option>
              <option value="name_asc">Sort: Name A-Z</option>
              <option value="name_desc">Sort: Name Z-A</option>
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      {exams.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 flex items-center justify-center">
            <svg className="w-8 h-8 text-indigo-400 dark:text-indigo-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-700 dark:text-slate-300 mb-2">No exams yet</h3>
          <p className="text-gray-500 dark:text-slate-400 mb-6">Create your first exam to get started with AI grading.</p>
          <Link to="/grade" className="btn-primary inline-flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create First Exam
          </Link>
        </div>
      ) : visibleExams.length === 0 ? (
        <div className="card p-10 text-center">
          <h3 className="text-base font-semibold text-gray-700 dark:text-slate-300 mb-1">No matching exams</h3>
          <p className="text-sm text-gray-500 dark:text-slate-400">Try a different search term.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleExams.map((exam, index) => (
            <div
              key={exam.id}
              role="button"
              tabIndex={0}
              onClick={(e) => { if (!e.target.closest('button, a')) openExam(exam) }}
              onKeyDown={(e) => {
                const isInteractive =
                  !!e.target.closest('button, a, input, textarea, select, [contenteditable="true"]')
                if ((e.key === 'Enter' || e.key === ' ') && !isInteractive) {
                  e.preventDefault()
                  openExam(exam)
                }
              }}
              className="card p-5 animate-fade-in cursor-pointer hover:ring-2 hover:ring-indigo-200 dark:hover:ring-indigo-700 transition-shadow"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    {editingExamId === exam.id ? (
                      <div className="flex items-center gap-2 min-w-0">
                        <input
                          value={editingExamName}
                          onChange={(e) => setEditingExamName(e.target.value)}
                          onClick={(e) => e.stopPropagation()}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              e.preventDefault()
                              e.stopPropagation()
                              saveRename(exam)
                            } else if (e.key === 'Escape') {
                              e.preventDefault()
                              e.stopPropagation()
                              cancelRename()
                            }
                          }}
                          className="px-2 py-1 border border-gray-300 dark:border-slate-600 rounded-md text-sm w-64 max-w-full bg-white dark:bg-slate-800 text-gray-900 dark:text-slate-100 focus:ring-indigo-500 focus:border-indigo-500"
                          autoFocus
                        />
                        <button
                          onClick={(e) => { e.stopPropagation(); saveRename(exam) }}
                          disabled={renaming}
                          className="px-2 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800 rounded-md hover:bg-emerald-50 dark:hover:bg-emerald-950/40 disabled:opacity-50"
                        >
                          Save
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); cancelRename() }}
                          disabled={renaming}
                          className="px-2 py-1 text-xs font-medium text-gray-600 dark:text-slate-300 border border-gray-200 dark:border-slate-600 rounded-md hover:bg-gray-50 dark:hover:bg-slate-800 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 min-w-0">
                        <h2 className="text-base font-semibold text-gray-900 dark:text-white truncate">
                          {exam.name}
                        </h2>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); startRename(exam) }}
                          className="p-1 -m-1 rounded-md text-gray-900 dark:text-white hover:bg-gray-100/90 dark:hover:bg-white/10 transition-colors flex-shrink-0"
                          title="Rename exam"
                          aria-label={`Rename exam ${exam.name}`}
                        >
                          <svg
                            className="w-[1.1em] h-[1.1em] block"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                            aria-hidden
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2.25}
                              d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L12 15l-4 1 1-4 8.586-8.586z"
                            />
                          </svg>
                        </button>
                      </div>
                    )}
                    {getStatusBadge(exam.status)}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500 dark:text-slate-400">
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" />
                      </svg>
                      {exam.student_count || 0} students
                    </span>
                    <span className="flex items-center gap-1">
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      {new Date(exam.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="flex flex-none flex-row items-center gap-2">
                  {exam.status === 'completed' && (
                    <>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate(`/exams/${exam.id}/results`)
                        }}
                        className={`${examRowActionClass} text-indigo-600 dark:text-indigo-400 border-indigo-200 dark:border-indigo-800 hover:bg-indigo-50 dark:hover:bg-indigo-950/40`}
                      >
                        Results
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          navigate('/grade', { state: { examId: exam.id, examName: exam.name, regrade: true } })
                        }}
                        className={`${examRowActionClass} text-orange-600 dark:text-orange-400 border-orange-200 dark:border-orange-800 hover:bg-orange-50 dark:hover:bg-orange-950/40`}
                      >
                        Regrade
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          downloadExcel(exam.id, exam.name)
                        }}
                        className={`${examRowActionClass} text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800 hover:bg-emerald-50 dark:hover:bg-emerald-950/40`}
                      >
                        Excel
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation()
                          downloadAllPDFs(exam.id, exam.name)
                        }}
                        className={`${examRowActionClass} text-purple-600 dark:text-purple-400 border-purple-200 dark:border-purple-800 hover:bg-purple-50 dark:hover:bg-purple-950/40`}
                      >
                        PDFs
                      </button>
                    </>
                  )}
                  {exam.status === 'grading' && (
                    <span className="flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 px-3 py-1.5">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Grading...
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      setDeleteTarget({ id: exam.id, name: exam.name })
                    }}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-red-50 hover:text-red-500 dark:text-slate-500 dark:hover:bg-red-950/40 dark:hover:text-red-400"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {deleteTarget && (
        <div className="fixed inset-0 z-[1000] flex items-center justify-center bg-slate-900/55 backdrop-blur-[1px] p-4">
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 shadow-2xl border border-gray-100 dark:border-slate-700">
            <div className="p-5">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Delete Exam?</h3>
              <p className="mt-2 text-sm text-gray-600 dark:text-slate-400">
                Are you sure you want to delete{' '}
                <span className="font-medium text-gray-900 dark:text-slate-100">{deleteTarget.name}</span>?
                This action cannot be undone.
              </p>
            </div>
            <div className="flex items-center justify-end gap-2 px-5 py-4 border-t border-gray-100 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/80 rounded-b-2xl">
              <button
                onClick={() => setDeleteTarget(null)}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-slate-200 border border-gray-300 dark:border-slate-600 rounded-lg hover:bg-white dark:hover:bg-slate-700 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(deleteTarget.id)}
                disabled={deleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ExamList
