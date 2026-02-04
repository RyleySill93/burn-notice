import { useNavigate, Link } from 'react-router'
import { useEffect, useState, useRef } from 'react'
import { githubCallback } from '@/generated/github/github'

export function GitHubCallbackPage() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(true)

  // Get query params
  const searchParams = new URLSearchParams(window.location.search)
  const code = searchParams.get('code')
  const state = searchParams.get('state')

  // Use ref to prevent double-execution in React Strict Mode
  const hasProcessed = useRef(false)

  useEffect(() => {
    const handleCallback = async () => {
      if (hasProcessed.current) return
      hasProcessed.current = true

      if (!code || !state) {
        setError('Invalid GitHub callback: missing code or state')
        setIsProcessing(false)
        return
      }

      try {
        await githubCallback({ code, state })

        // Success - redirect to setup page
        navigate('/setup', { replace: true })
      } catch (err: any) {
        const errorMessage =
          err?.response?.data?.detail || err?.message || 'GitHub authentication failed'
        setError(errorMessage)
        setIsProcessing(false)
      }
    }

    handleCallback()
  }, [code, state, navigate])

  if (isProcessing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
          <p className="mt-4">Connecting GitHub...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-600 text-xl font-semibold">GitHub Connection Failed</div>
          <p className="mt-2 text-gray-600">{error}</p>
          <Link
            to="/setup"
            className="mt-4 inline-block text-blue-600 hover:text-blue-500"
          >
            Back to Setup
          </Link>
        </div>
      </div>
    )
  }

  return null
}
