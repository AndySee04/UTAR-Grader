import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { gradingAPI, reportsAPI } from '../services/api'
import { useToast } from '../context/ToastContext'

function ExamResults() {
  const { examId } = useParams()
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedStudent, setSelectedStudent] = useState(null)
  const [editingGrade, setEditingGrade] = useState(null)
  const [editScore, setEditScore] = useState('')
  const toast = useToast()

  useEffect(() => {
    loadResults()
  }, [examId])

  const loadResults = async () => {
    try {
      const res = await gradingAPI.getGrades(examId)
      setResults(res.data)
      return res.data
    } catch (err) {
      setError('Failed to load results')
      return null
    } finally {
      setLoading(false)
    }
  }

  const handleOverrideScore = async (gradeId) => {
    const score = parseFloat(editScore)
    if (isNaN(score) || score < 0) {
      toast.error('Please enter a valid score')
      return
    }

    try {
      await gradingAPI.overrideGrade(gradeId, { score })
      toast.success('Score updated')
      setEditingGrade(null)
      setEditScore('')
      // Reload to get updated totals and get fresh data
      const data = await loadResults()
      // Re-select the student to refresh their grades
      if (selectedStudent && data?.students) {
        const updated = data.students.find(s => s.document_id === selectedStudent.document_id)
        if (updated) setSelectedStudent(updated)
      }
    } catch (err) {
      toast.error('Failed to update score')
    }
  }

  const downloadStudentPDF = async (docId, studentName) => {
    try {
      toast.info('Preparing PDF...')
      const res = await reportsAPI.downloadStudentPDF(examId, docId)
      const url = window.URL.createObjectURL(new Blob([res.data]))
      const link = document.createElement('a')
      link.href = url
      link.download = `${studentName}_report.pdf`
      link.click()
      toast.success('Download started')
    } catch (err) {
      toast.error('Failed to download report')
    }
  }

  const getConfidenceMeta = (confidence) => {
    const c = Math.max(0, Math.min(1, Number(confidence)))
    if (c >= 0.8) {
      return { label: 'High', className: 'text-emerald-700 bg-emerald-50 border-emerald-100' }
    }
    if (c >= 0.6) {
      return { label: 'Medium', className: 'text-amber-700 bg-amber-50 border-amber-100' }
    }
    return { label: 'Low', className: 'text-red-700 bg-red-50 border-red-100' }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="skeleton h-8 w-64" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="card p-4 space-y-3">
            {[1, 2, 3, 4].map(i => <div key={i} className="skeleton h-12 w-full" />)}
          </div>
          <div className="lg:col-span-2 card p-8">
            <div className="skeleton h-6 w-48 mx-auto" />
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded-xl text-sm">
        {error}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:justify-between sm:items-start gap-4">
        <div>
          <Link to="/exams" className="text-sm text-indigo-600 hover:text-indigo-500 flex items-center gap-1 mb-2 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
            Back to Exams
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">{results?.exam_name}</h1>
        </div>

        {/* Stats cards */}
        <div className="flex gap-3">
          <div className="bg-indigo-50/50 rounded-xl px-4 py-2 border border-indigo-100 text-center">
            <p className="text-xs font-medium text-indigo-500 uppercase tracking-wide">Graded</p>
            <p className="text-lg font-bold text-indigo-700">
              {results?.graded_students}/{results?.total_students}
            </p>
          </div>
          {results?.average_percentage != null && (
            <div className="bg-emerald-50/50 rounded-xl px-4 py-2 border border-emerald-100 text-center">
              <p className="text-xs font-medium text-emerald-500 uppercase tracking-wide">Average</p>
              <p className="text-lg font-bold text-emerald-700">
                {results.average_percentage.toFixed(1)}%
              </p>
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Student List */}
        <div className="card-flat overflow-hidden">
          <div className="p-4 bg-gray-50/80 border-b border-gray-100">
            <h2 className="text-sm font-semibold text-gray-700">Students</h2>
          </div>
          <div className="divide-y divide-gray-50 max-h-[500px] overflow-y-auto">
            {results?.students?.map((student) => (
              <div
                key={student.document_id}
                onClick={() => setSelectedStudent(student)}
                className={`p-4 cursor-pointer transition-all duration-150 ${
                  selectedStudent?.document_id === student.document_id
                    ? 'bg-indigo-50 border-l-2 border-l-indigo-500'
                    : 'hover:bg-gray-50/80 border-l-2 border-l-transparent'
                }`}
              >
                <div className="flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-semibold ${
                      student.percentage >= 80 ? 'bg-emerald-100 text-emerald-700' :
                      student.percentage >= 50 ? 'bg-amber-100 text-amber-700' :
                      'bg-red-100 text-red-700'
                    }`}>
                      {(student.student_name || '?')[0].toUpperCase()}
                    </div>
                    <span className="font-medium text-sm text-gray-800">{student.student_name || 'Unknown'}</span>
                  </div>
                  <div className="text-right">
                    <span className={`text-sm font-bold ${
                      student.percentage >= 80 ? 'text-emerald-600' :
                      student.percentage >= 50 ? 'text-amber-600' :
                      'text-red-600'
                    }`}>
                      {student.percentage.toFixed(1)}%
                    </span>
                    <p className="text-xs text-gray-400">
                      {student.total_score.toFixed(1)}/{student.total_max_marks.toFixed(1)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Grade Details */}
        <div className="lg:col-span-2 card-flat overflow-hidden">
          {selectedStudent ? (
            <>
              <div className="p-4 bg-gray-50/80 border-b border-gray-100 flex justify-between items-center">
                <div>
                  <h2 className="font-semibold text-gray-900">{selectedStudent.student_name}</h2>
                  <p className="text-sm text-gray-500">
                    {selectedStudent.total_score.toFixed(1)} / {selectedStudent.total_max_marks.toFixed(1)} marks
                    <span className={`ml-2 font-semibold ${
                      selectedStudent.percentage >= 50 ? 'text-emerald-600' : 'text-red-600'
                    }`}>
                      ({selectedStudent.percentage.toFixed(1)}%)
                    </span>
                  </p>
                </div>
                <button
                  onClick={() => downloadStudentPDF(selectedStudent.document_id, selectedStudent.student_name)}
                  className="btn-primary text-sm flex items-center gap-1.5"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  PDF
                </button>
              </div>
              <div className="p-4 space-y-3 max-h-[500px] overflow-y-auto">
                {selectedStudent.grades.map((grade, i) => (
                  <div key={i} className="border border-gray-100 rounded-xl p-4 hover:border-gray-200 transition-colors animate-fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold bg-gray-100 text-gray-600 px-2 py-0.5 rounded-md">
                          {grade.question_number}
                        </span>
                        {grade.is_overridden && (
                          <span className="text-xs font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md flex items-center gap-1">
                            <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                            Overridden
                          </span>
                        )}
                      </div>

                      {/* Score display / edit */}
                      <div className="flex items-center gap-2">
                        {grade.confidence != null && (() => {
                          const meta = getConfidenceMeta(grade.confidence)
                          return (
                            <span className={`text-[11px] font-semibold border px-2 py-0.5 rounded-md ${meta.className}`}>
                              Confidence: {meta.label}
                            </span>
                          )
                        })()}
                        {editingGrade === grade.id ? (
                          <div className="flex items-center gap-1.5">
                            <input
                              type="number"
                              value={editScore}
                              onChange={(e) => setEditScore(e.target.value)}
                              className="w-16 px-2 py-1 border border-indigo-300 rounded-lg text-sm text-right focus:ring-indigo-500"
                              step="0.5"
                              min="0"
                              max={grade.max_marks}
                              autoFocus
                            />
                            <span className="text-sm text-gray-400">/ {grade.max_marks?.toFixed(1)}</span>
                            <button
                              onClick={() => handleOverrideScore(grade.id)}
                              className="p-1 text-emerald-600 hover:bg-emerald-50 rounded transition-colors"
                              title="Save"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                            </button>
                            <button
                              onClick={() => { setEditingGrade(null); setEditScore('') }}
                              className="p-1 text-gray-400 hover:bg-gray-100 rounded transition-colors"
                              title="Cancel"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <span className={`text-sm font-bold ${
                              (grade.score / grade.max_marks) >= 0.5 ? 'text-emerald-600' : 'text-red-600'
                            }`}>
                              {grade.score?.toFixed(1)} / {grade.max_marks?.toFixed(1)}
                            </span>
                            <button
                              onClick={() => { setEditingGrade(grade.id); setEditScore(String(grade.score || 0)) }}
                              className="p-1 text-gray-400 hover:text-indigo-600 hover:bg-indigo-50 rounded transition-all"
                              title="Override score"
                            >
                              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                              </svg>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    {grade.question_text && (
                      <p className="text-sm text-gray-600 mb-1 font-medium">
                        {grade.question_text}
                      </p>
                    )}

                    {grade.answer_scheme && (
                      <p className="text-xs text-gray-500 mb-1">
                        <span className="font-semibold uppercase tracking-wide">Answer guide:</span>
                        <br />
                        <span className="whitespace-pre-wrap">
                          {(grade.answer_scheme || '').trimStart()}
                        </span>
                      </p>
                    )}

                    {grade.student_answer && (
                      <div className="mb-2 rounded-lg border border-gray-100 bg-gray-50/80 px-3 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-gray-400 mb-0.5">
                          Student answer
                        </p>
                        <p className="text-sm text-gray-700 whitespace-pre-wrap">
                          {grade.student_answer}
                        </p>
                      </div>
                    )}

                    {grade.feedback && (
                      <div className="rounded-lg border border-indigo-100 bg-indigo-50/40 px-3 py-2">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-indigo-500 mb-0.5">
                          AI feedback
                        </p>
                        <p className="text-sm text-gray-700 whitespace-pre-wrap">
                          {grade.feedback}
                        </p>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-gray-400">
              <svg className="w-12 h-12 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              <p className="text-sm font-medium">Select a student to view grades</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ExamResults
