import { useNavigate, useParams, Link } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState } from 'react'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { SuperFormProvider } from '@/components/SuperFormProvider'
import { Input } from '@/components/ui/input'
import { useApiError } from '@/hooks/useApiError'
import { ArrowLeft, CheckCircle } from 'lucide-react'
import { useUpdatePassword } from '@/generated/auth/auth'
import { authService } from '@/services/authService'

const resetPasswordSchema = z.object({
  password: z.string()
    .min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: 'Passwords do not match',
  path: ['confirmPassword'],
})

type ResetPasswordFormValues = z.infer<typeof resetPasswordSchema>

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const { userId, token } = useParams<{ userId: string; token: string }>()
  const [passwordReset, setPasswordReset] = useState(false)
  const apiError = useApiError()
  const updatePasswordMutation = useUpdatePassword()

  const handleSubmit = async (data: ResetPasswordFormValues) => {
    if (!userId || !token) return
    
    const response = await updatePasswordMutation.mutateAsync({
      data: {
        passwordString: data.password,
        token: token,
      },
      params: {
        user_id: userId,
      },
    })
    
    // Check if we received auth tokens (auto-login after password reset)
    if (response && 'accessToken' in response && response.accessToken) {
      authService.handleAuthentication(response.accessToken, response.refreshToken)
      navigate('/')
      window.location.reload()
    } else {
      // Fallback: show success message if no tokens returned
      setPasswordReset(true)
    }
  }

  if (passwordReset) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <CheckCircle className="mx-auto h-12 w-12 text-green-600" />
            <h2 className="mt-4 text-3xl font-bold">Password reset successful</h2>
            <p className="mt-2 text-gray-600">
              Your password has been successfully reset. You can now sign in with your new password.
            </p>
          </div>

          <Link to="/login" className="block">
            <SuperButton className="w-full">
              Go to login
            </SuperButton>
          </Link>
        </div>
      </div>
    )
  }

  if (!userId || !token) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold">Invalid reset link</h2>
            <p className="mt-2 text-gray-600">
              This password reset link is invalid or has expired.
            </p>
          </div>

          <div className="space-y-3">
            <Link to="/forgot-password" className="block">
              <SuperButton className="w-full">
                Request a new link
              </SuperButton>
            </Link>

            <Link to="/login" className="block">
              <SuperButton variant="ghost" className="w-full">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to login
              </SuperButton>
            </Link>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md space-y-8 p-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Reset your password</h2>
          <p className="mt-2 text-gray-600">
            Enter your new password below.
          </p>
        </div>

        {apiError.ErrorAlert}

        <SuperFormProvider
          config={{
            resolver: zodResolver(resetPasswordSchema),
            defaultValues: {
              password: '',
              confirmPassword: '',
            },
          }}
          onSubmit={handleSubmit}
          apiError={apiError}
          className="mt-8 space-y-6"
        >
          {(form) => (
            <>
              <div className="space-y-4">
                <SuperField
                  label="New password"
                  name="password"
                  errorText={form.formState.errors.password?.message}
                  helperText="Must be at least 8 characters"
                >
                  <Input
                    type="password"
                    {...form.register('password')}
                  />
                </SuperField>

                <SuperField
                  label="Confirm new password"
                  name="confirmPassword"
                  errorText={form.formState.errors.confirmPassword?.message}
                >
                  <Input
                    type="password"
                    {...form.register('confirmPassword')}
                  />
                </SuperField>
              </div>

              <div className="space-y-3">
                <SuperButton type="submit" className="w-full">
                  Reset password
                </SuperButton>

                <Link to="/login" className="block">
                  <SuperButton variant="ghost" className="w-full">
                    <ArrowLeft className="mr-2 h-4 w-4" />
                    Back to login
                  </SuperButton>
                </Link>
              </div>
            </>
          )}
        </SuperFormProvider>
      </div>
    </div>
  )
}