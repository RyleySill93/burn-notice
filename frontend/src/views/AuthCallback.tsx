import { useNavigate, Link } from 'react-router'
import { useEffect, useState } from 'react'
import { authService } from '@/services/authService'
import { useAuthenticateEmailChallenge } from '@/generated/auth/auth'

export function AuthCallback() {
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)
  const [isProcessing, setIsProcessing] = useState(true)

  // Get query params
  const searchParams = new URLSearchParams(window.location.search)
  const userId = searchParams.get('user_id')
  const token = searchParams.get('token')
  
  const authenticateEmailChallengeMutation = useAuthenticateEmailChallenge()

  useEffect(() => {
    const authenticate = async () => {
      if (!userId || !token) {
        setError('Invalid authentication link')
        setIsProcessing(false)
        return
      }

      try {
        const data = await authenticateEmailChallengeMutation.mutateAsync({
          userId: userId,
          token: token,
        })

        // Check if MFA is required (MfaToken has 'token' property, Token has 'accessToken')
        if ('token' in data && !('accessToken' in data)) {
          // Cast to MfaToken type
          const mfaData = data as any
          // Store MFA token and redirect to MFA page
          sessionStorage.setItem('mfa_token', mfaData.token)
          sessionStorage.setItem('mfa_email', '')
          navigate('/auth/mfa')
        } else if ('accessToken' in data) {
          // Cast to Token type
          const tokenData = data as any
          // Store tokens and redirect to home (Token type)
          authService.handleAuthentication(tokenData.accessToken, tokenData.refreshToken)
          navigate('/')
          window.location.reload() // Refresh to update auth state
        } else {
          throw new Error('Unexpected response format')
        }
      } catch (err: any) {
        setError(err.message || 'Authentication failed')
      } finally {
        setIsProcessing(false)
      }
    }

    authenticate()
  }, [userId, token, navigate, authenticateEmailChallengeMutation])

  if (isProcessing) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
          <p className="mt-4">Authenticating...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <div className="text-red-600 text-xl font-semibold">Authentication Failed</div>
          <p className="mt-2 text-gray-600">{error}</p>
          <Link to="/login" className="mt-4 inline-block text-blue-600 hover:text-blue-500">
            Back to login
          </Link>
        </div>
      </div>
    )
  }

  return null
}