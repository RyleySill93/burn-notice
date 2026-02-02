import { useNavigate, Link, Navigate } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { SuperFormProvider } from '@/components/SuperFormProvider'
import { Input } from '@/components/ui/input'
import { useApiError } from '@/hooks/useApiError'
import { useAuthenticateMfa } from '@/generated/auth/auth'
import { authService } from '@/services/authService'
import { config } from '@/config/app'

const loginSchema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(1, 'Password is required'),
})

const mfaSchema = z.object({
  mfaCode: z.string().length(6, 'Code must be 6 digits').regex(/^\d+$/, 'Code must be numeric'),
})

type LoginFormValues = z.infer<typeof loginSchema>
type MfaFormValues = z.infer<typeof mfaSchema>

export function LoginPage() {
  const navigate = useNavigate()
  const { login, loginWithMagicLink, isAuthenticated } = useAuth()
  const [magicLinkSent, setMagicLinkSent] = useState(false)
  const apiError = useApiError()
  const [showPassword, setShowPassword] = useState(true)
  const [mfaToken, setMfaToken] = useState<string | null>(null)
  const [savedEmail, setSavedEmail] = useState('')
  
  const authenticateMfaMutation = useAuthenticateMfa()

  const loginConfig = {
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  }

  const mfaConfig = {
    resolver: zodResolver(mfaSchema),
    defaultValues: {
      mfaCode: '',
    },
  }

  // Redirect if already authenticated
  if (isAuthenticated) {
    return <Navigate to="/" replace />
  }

  const handlePasswordLogin = async (data: LoginFormValues) => {
    setSavedEmail(data.email)

    try {
      await login(data.email, data.password)
      navigate('/')
    } catch (err: any) {
      // Check if MFA is required
      if (err.message?.startsWith('MFA_REQUIRED:')) {
        const token = err.message.split(':')[1]
        setMfaToken(token)
        setShowPassword(false)
      } else {
        // Re-throw to let SuperFormProvider handle it
        throw err
      }
    }
  }

  const handleMagicLink = async (email: string) => {
    if (!email) return

    setSavedEmail(email)

    try {
      apiError.clearError()
      await loginWithMagicLink(email)
      setMagicLinkSent(true)
    } catch (err) {
      apiError.setError(err)
    }
  }

  const handleMfaSubmit = async (data: MfaFormValues) => {
    const response = await authenticateMfaMutation.mutateAsync({
      data: {
        email: savedEmail,
        mfaCode: data.mfaCode,
        mfaToken: mfaToken!,
        mfaMethod: 'EMAIL', // Default to email, can be changed for TOTP/SMS
      },
    })

    // Store tokens and redirect
    authService.handleAuthentication(response.accessToken, response.refreshToken)
    navigate('/')
    window.location.reload() // Refresh to update auth state
  }

  if (magicLinkSent) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold">Check your email</h2>
            <p className="mt-2 text-gray-600">We've sent a magic link to {savedEmail}</p>
            <p className="mt-4 text-sm text-gray-500">
              Click the link in the email to sign in to your account.
            </p>
            <SuperButton
              onClick={() => {
                setMagicLinkSent(false)
              }}
              className="mt-6"
              variant="outline"
            >
              Back to login
            </SuperButton>
          </div>
        </div>
      </div>
    )
  }

  if (mfaToken) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold">Two-Factor Authentication</h2>
            <p className="mt-2 text-gray-600">
              Enter the verification code from your authenticator app
            </p>
          </div>

          {apiError.ErrorAlert}
          
          <SuperFormProvider
            config={mfaConfig}
            onSubmit={handleMfaSubmit}
            apiError={apiError}
            className="mt-8 space-y-6"
          >
            {(form) => (
              <>

                <SuperField
                  name="mfaCode"
                  label="Verification Code"
                  errorText={form.formState.errors.mfaCode?.message}
                >
                  <Input
                    type="text"
                    placeholder="Enter 6-digit code"
                    maxLength={6}
                    className="text-center text-lg"
                    {...form.register('mfaCode')}
                  />
                </SuperField>

                <div className="space-y-3">
                  <SuperButton 
                    type="submit" 
                    className="w-full"
                  >
                    Verify
                  </SuperButton>

                  <SuperButton
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => {
                      setMfaToken(null)
                      form.reset()
                      setShowPassword(true)
                    }}
                  >
                    Back to login
                  </SuperButton>
                </div>
              </>
            )}
          </SuperFormProvider>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md space-y-8 p-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Sign in to {config.projectName}</h2>
          <p className="mt-2 text-gray-600">Enter your email to sign in to your account</p>
        </div>

        {apiError.ErrorAlert}
        
        <SuperFormProvider
          config={loginConfig}
          onSubmit={handlePasswordLogin}
          apiError={apiError}
          className="mt-8 space-y-6"
        >
          {(form) => (
            <>

              <div className="space-y-4">
                <SuperField
                  label="Email address"
                  name="email"
                  errorText={form.formState.errors.email?.message}
                >
                  <Input
                    type="email"
                    {...form.register('email')}
                  />
                </SuperField>

                {showPassword && (
                  <SuperField
                    label={
                      <div className="flex items-center justify-between w-full gap-2">
                        <span>Password</span>
                        <Link 
                          to="/forgot-password" 
                          className="text-sm font-normal text-blue-600 hover:text-blue-500 ml-auto"
                          tabIndex={-1}
                        >
                          Forgot your password?
                        </Link>
                      </div>
                    }
                    name="password"
                    errorText={form.formState.errors.password?.message}
                  >
                    <Input
                      type="password"
                      {...form.register('password')}
                    />
                  </SuperField>
                )}
              </div>

              <div className="space-y-3">
                {showPassword && (
                  <SuperButton 
                    type="submit" 
                    className="w-full"
                  >
                    Sign in with password
                  </SuperButton>
                )}

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-white px-2 text-gray-500">Or</span>
                  </div>
                </div>

                <SuperButton
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => handleMagicLink(form.getValues('email'))}
                >
                  Send magic link
                </SuperButton>
              </div>

              <div className="text-center text-sm">
                <Link to="/signup" className="font-medium text-blue-600 hover:text-blue-500">
                  Don't have an account? Sign up
                </Link>
              </div>
            </>
          )}
        </SuperFormProvider>
      </div>
    </div>
  )
}