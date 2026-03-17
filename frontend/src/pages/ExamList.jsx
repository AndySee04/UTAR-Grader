import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { examsAPI, reportsAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

function ExamList() {
  const [exams, setExams] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
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
    if (!confirm('Are you sure you want to delete this exam? This action cannot be undone.')) return

    try {
      await examsAPI.delete(id)
      setExams(exams.filter(e => e.id !== id))
      toast.success('Exam deleted')
    } catch (err) {
      toast.error('Failed to delete exam')
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
          <h1 className="text-2xl font-bold text-gray-900">My Exams</h1>
          <p className="text-sm text-gray-500 mt-1">{exams.length} exam{exams.length !== 1 ? 's' : ''} total</p>
        </div>
        <Link to="/grade" className="btn-primary flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Exam
        </Link>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl text-sm">
          {error}
        </div>
      )}

      {exams.length === 0 ? (
        <div className="card p-16 text-center">
          <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-indigo-50 flex items-center justify-center">
            <svg className="w-8 h-8 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-gray-700 mb-2">No exams yet</h3>
          <p className="text-gray-500 mb-6">Create your first exam to get started with AI grading.</p>
          <Link to="/grade" className="btn-primary inline-flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Create First Exam
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {exams.map((exam, index) => (
            <div
              key={exam.id}
              role="button"
              tabIndex={0}
              onClick={(e) => { if (!e.target.closest('button, a')) openExam(exam) }}
              onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && !e.target.closest('button, a')) { e.preventDefault(); openExam(exam) } }}
              className="card p-5 animate-fade-in cursor-pointer hover:ring-2 hover:ring-indigo-200 transition-shadow"
              style={{ animationDelay: `${index * 50}ms` }}
            >
              <div className="flex flex-col sm:flex-row sm:justify-between sm:items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-2">
                    <h2 className="text-base font-semibold text-gray-900 truncate">{exam.name}</h2>
                    {getStatusBadge(exam.status)}
                  </div>
                  <div className="flex items-center gap-4 text-sm text-gray-500">
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

                <div className="flex items-center gap-2 flex-shrink-0">
                  {exam.status === 'completed' && (
                    <>
                      <Link
                        to={`/exams/${exam.id}/results`}
                        className="px-3 py-1.5 text-sm font-medium text-indigo-600 border border-indigo-200 rounded-lg hover:bg-indigo-50 transition-colors"
                      >
                        Results
                      </Link>
                      <button
                        onClick={() => navigate('/grade', { state: { examId: exam.id, examName: exam.name, regrade: true } })}
                        className="px-3 py-1.5 text-sm font-medium text-orange-600 border border-orange-200 rounded-lg hover:bg-orange-50 transition-colors"
                      >
                        Regrade
                      </button>
                      <button
                        onClick={() => downloadExcel(exam.id, exam.name)}
                        className="px-3 py-1.5 text-sm font-medium text-emerald-600 border border-emerald-200 rounded-lg hover:bg-emerald-50 transition-colors"
                      >
                        Excel
                      </button>
                      <button
                        onClick={() => downloadAllPDFs(exam.id, exam.name)}
                        className="px-3 py-1.5 text-sm font-medium text-purple-600 border border-purple-200 rounded-lg hover:bg-purple-50 transition-colors"
                      >
                        PDFs
                      </button>
                    </>
                  )}
                  {exam.status === 'grading' && (
                    <span className="flex items-center gap-2 text-sm text-blue-600 px-3 py-1.5">
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Grading...
                    </span>
                  )}
                  <button
                    onClick={() => handleDelete(exam.id)}
                    className="p-1.5 text-gray-400 hover:text-red-500 rounded-lg hover:bg-red-50 transition-all"
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
    </div>
  )
}

export default ExamList
