import { useNavigate, Link } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState } from 'react'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { SuperFormProvider } from '@/components/SuperFormProvider'
import { Input } from '@/components/ui/input'
import { useApiError } from '@/hooks/useApiError'
import { useSignup } from '@/generated/auth/auth'
import { authService } from '@/services/authService'
import { config } from '@/config/app'

const signupSchema = z.object({
  email: z.string().email('Invalid email address'),
  firstName: z.string().min(1, 'First name is required').trim(),
  lastName: z.string().min(1, 'Last name is required').trim(),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string().min(8, 'Password must be at least 8 characters'),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords do not match",
  path: ["confirmPassword"],
})

type SignupFormValues = z.infer<typeof signupSchema>

export function SignupPage() {
  const navigate = useNavigate()
  const [signupComplete, setSignupComplete] = useState(false)
  const apiError = useApiError()
  
  const signupMutation = useSignup()

  // Form config for SuperFormProvider
  const formConfig = {
    resolver: zodResolver(signupSchema),
    defaultValues: {
      email: '',
      firstName: '',
      lastName: '',
      password: '',
      confirmPassword: '',
    },
  }

  const onSubmit = async (data: SignupFormValues) => {
    // Call signup endpoint using React Query mutation
    const response = await signupMutation.mutateAsync({
      data: {
        email: data.email,
        firstName: data.firstName,
        lastName: data.lastName,
        password: data.password,
      },
    })

    // If tokens are returned, handle authentication
    if (response.accessToken) {
      authService.handleAuthentication(response.accessToken, response.refreshToken)
      navigate('/')
      window.location.reload()
    } else {
      // Otherwise show success message
      setSignupComplete(true)
    }
  }

  if (signupComplete) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-full max-w-md space-y-8 p-8">
          <div className="text-center">
            <h2 className="text-3xl font-bold">Account Created!</h2>
            <p className="mt-2 text-gray-600">Your account has been created successfully.</p>
            <p className="mt-4 text-sm text-gray-500">
              Check your email for a verification link to activate your account.
            </p>
            <SuperButton onClick={() => navigate('/login')} className="mt-6">
              Go to Login
            </SuperButton>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-md space-y-8 p-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Create your account</h2>
          <p className="mt-2 text-gray-600">Get started with {config.projectName}</p>
        </div>

        {apiError.ErrorAlert}
        
        <SuperFormProvider 
          config={formConfig}
          onSubmit={onSubmit}
          apiError={apiError}
          className="mt-8 space-y-6"
        >
          {(form) => (
            <>

              <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <SuperField
                label="First name"
                name="firstName"
                errorText={form.formState.errors.firstName?.message}
              >
                <Input
                  type="text"
                  {...form.register('firstName')}
                />
              </SuperField>

              <SuperField
                label="Last name"
                name="lastName"
                errorText={form.formState.errors.lastName?.message}
              >
                <Input
                  type="text"
                  {...form.register('lastName')}
                />
              </SuperField>
            </div>

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

            <SuperField
              label="Password"
              name="password"
              helperText="Must be at least 8 characters"
              errorText={form.formState.errors.password?.message}
            >
              <Input
                type="password"
                {...form.register('password')}
              />
            </SuperField>

            <SuperField
              label="Confirm password"
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
            <SuperButton 
              type="submit" 
              className="w-full"
            >
              Create account
            </SuperButton>
          </div>

              <div className="text-center text-sm">
                <Link to="/login" className="font-medium text-blue-600 hover:text-blue-500">
                  Already have an account? Sign in
                </Link>
              </div>
            </>
          )}
        </SuperFormProvider>
      </div>
    </div>
  )
}