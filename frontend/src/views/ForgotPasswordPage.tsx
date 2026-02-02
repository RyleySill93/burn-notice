import { useState } from 'react'
import { Link } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { SuperFormProvider } from '@/components/SuperFormProvider'
import { Input } from '@/components/ui/input'
import { useApiError } from '@/hooks/useApiError'
import { ArrowLeft } from 'lucide-react'
import { useGeneratePasswordResetEmail } from '@/generated/auth/auth'

const forgotPasswordSchema = z.object({
  email: z.string().email('Invalid email address'),
})

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>

export function ForgotPasswordPage() {
  const [emailSent, setEmailSent] = useState(false)
  const [submittedEmail, setSubmittedEmail] = useState('')
  const apiError = useApiError()
  const generatePasswordResetEmailMutation = useGeneratePasswordResetEmail()

  const handleSubmit = async (data: ForgotPasswordFormValues) => {
    await generatePasswordResetEmailMutation.mutateAsync({
      data: {
        email: data.email,
      },
    })
    setSubmittedEmail(data.email)
    setEmailSent(true)
  }

  if (emailSent) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold">Check your email</h2>
            <p className="mt-2 text-gray-600">
              We've sent password reset instructions to {submittedEmail}
            </p>
            <p className="mt-4 text-sm text-gray-500">
              If you don't receive an email within a few minutes, check your spam folder.
            </p>
          </div>

          <div className="space-y-3">
            <SuperButton
              onClick={() => {
                setEmailSent(false)
                setSubmittedEmail('')
              }}
              variant="outline"
              className="w-full"
            >
              Send another email
            </SuperButton>

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
          <h2 className="text-3xl font-bold">Forgot your password?</h2>
          <p className="mt-2 text-gray-600">
            Enter your email address and we'll send you a link to reset your password.
          </p>
        </div>

        {apiError.ErrorAlert}

        <SuperFormProvider
          config={{
            resolver: zodResolver(forgotPasswordSchema),
            defaultValues: {
              email: '',
            },
          }}
          onSubmit={handleSubmit}
          apiError={apiError}
          className="mt-8 space-y-6"
        >
          {(form) => (
            <>
              <SuperField
                label="Email address"
                name="email"
                errorText={form.formState.errors.email?.message}
              >
                <Input
                  type="email"
                  placeholder="Enter your email"
                  {...form.register('email')}
                />
              </SuperField>

              <div className="space-y-3">
                <SuperButton type="submit" className="w-full">
                  Send reset link
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