import { useState, useCallback } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertCircle, XCircle } from 'lucide-react'
import { AxiosError } from 'axios'

interface ApiError {
  message: string
  code?: number
  field?: string
}

interface PydanticValidationError {
  loc: (string | number)[]
  msg: string
  type: string
  input?: unknown
}

interface BackendError {
  message?: string
  detail?: string | PydanticValidationError[]
  code?: number
}

export function useApiError() {
  const [error, setError] = useState<ApiError | null>(null)

  const handleError = useCallback((err: unknown) => {
    // Handle Axios errors (from React Query mutations)
    if (err && typeof err === 'object' && 'isAxiosError' in err) {
      const axiosError = err as AxiosError<BackendError>

      // Extract the message from the backend response
      let backendMessage = axiosError.response?.data?.message

      // Handle detail field - can be a string or Pydantic validation error array
      if (!backendMessage && axiosError.response?.data?.detail) {
        const detail = axiosError.response.data.detail
        if (typeof detail === 'string') {
          backendMessage = detail
        } else if (Array.isArray(detail) && detail.length > 0) {
          // Pydantic validation errors: [{loc: [...], msg: "...", type: "..."}]
          backendMessage = detail.map((e: PydanticValidationError) => e.msg).join('. ')
        }
      }

      if (backendMessage) {
        // Use the backend's custom message
        setError({
          message: backendMessage,
          code: axiosError.response?.status
        })
      } else {
        // Only show generic message if no backend message is available
        // In production, you might want to log these for debugging
        setError({ 
          message: 'Something went wrong. Please try again.',
          code: axiosError.response?.status 
        })
      }
    } else if (err instanceof Error) {
      // Handle regular Error objects
      // Check if this is an error we threw (like MFA_REQUIRED)
      if (err.message.startsWith('MFA_REQUIRED:')) {
        // Don't show MFA errors as they're handled differently
        return
      }
      setError({ message: err.message })
    } else if (typeof err === 'object' && err !== null) {
      // Handle API response errors (legacy, shouldn't hit this with React Query)
      const apiError = err as { message?: string; detail?: string | PydanticValidationError[]; code?: number; status?: number; field?: string }
      let message = apiError.message
      if (!message && apiError.detail) {
        if (typeof apiError.detail === 'string') {
          message = apiError.detail
        } else if (Array.isArray(apiError.detail) && apiError.detail.length > 0) {
          message = apiError.detail.map((e: PydanticValidationError) => e.msg).join('. ')
        }
      }
      if (message) {
        setError({
          message,
          code: apiError.code || apiError.status,
          field: apiError.field,
        })
      } else {
        setError({ message: 'Something went wrong. Please try again.' })
      }
    } else if (typeof err === 'string') {
      // Handle string errors
      setError({ message: err })
    } else {
      // Fallback for unknown error types
      setError({ message: 'Something went wrong. Please try again.' })
    }
  }, [])

  const clearError = useCallback(() => {
    setError(null)
  }, [])

  const ErrorAlert = error ? (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Error</AlertTitle>
      <AlertDescription>
        {error.message}
        {error.field && ` (Field: ${error.field})`}
      </AlertDescription>
      <button
        onClick={clearError}
        type="button"
        className="absolute right-2 top-2 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
        aria-label="Close"
      >
        <XCircle className="h-4 w-4" />
      </button>
    </Alert>
  ) : null

  return {
    error,
    setError: handleError,
    clearError,
    ErrorAlert,
  }
}