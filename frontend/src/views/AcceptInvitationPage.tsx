import { useState } from 'react'
import { useSearchParams, useNavigate } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { CheckCircle, XCircle, Clock, Users } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { SuperField } from '@/components/SuperField'
import { SuperButton } from '@/components/SuperButton'
import { SuperFormProvider } from '@/components/SuperFormProvider'
import { useApiError } from '@/hooks/useApiError'
import {
  useGetInvitationByToken,
  useAcceptInvitation,
} from '@/generated/invitations/invitations'
import { useAuth } from '@/contexts/AuthContext'
import { authService } from '@/services/authService'

const signupSchema = z.object({
  firstName: z.string().min(1, 'First name is required'),
  lastName: z.string().min(1, 'Last name is required'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "Passwords don't match",
  path: ['confirmPassword'],
})

type SignupFormValues = z.infer<typeof signupSchema>

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token')
  const { isAuthenticated, user, setCurrentCustomerId } = useAuth()
  const apiError = useApiError()
  const [accepted, setAccepted] = useState(false)

  const { data: invitation, isLoading, error } = useGetInvitationByToken(
    { token: token ?? '' },
    { query: { enabled: !!token } }
  )

  const acceptMutation = useAcceptInvitation()

  // Check if user already has this email
  const isExistingUser = user?.email?.toLowerCase() === invitation?.email?.toLowerCase()

  const handleAcceptAndLogin = async (payload: { token: string; firstName?: string; lastName?: string; password?: string }) => {
    apiError.clearError()
    try {
      const response = await acceptMutation.mutateAsync({ data: payload })

      // Store the tokens
      authService.handleAuthentication(response.accessToken, response.refreshToken)

      // Set the current customer to the one they were invited to
      setCurrentCustomerId(response.customerId)

      setAccepted(true)

      // Redirect after a short delay
      setTimeout(() => navigate('/projects'), 1500)
    } catch (err) {
      apiError.setError(err)
    }
  }

  const handleAcceptForExistingUser = async () => {
    if (!token) return
    await handleAcceptAndLogin({ token })
  }

  const handleAcceptForNewUser = async (data: SignupFormValues) => {
    if (!token) return
    await handleAcceptAndLogin({
      token,
      firstName: data.firstName,
      lastName: data.lastName,
      password: data.password,
    })
  }

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <CardTitle>Invalid Invitation</CardTitle>
            <CardDescription>
              No invitation token was provided. Please check your invitation link.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  if (error || !invitation) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <CardTitle>Invitation Not Found</CardTitle>
            <CardDescription>
              This invitation may have expired or been revoked.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (invitation.status === 'ACCEPTED') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <CardTitle>Already Accepted</CardTitle>
            <CardDescription>
              This invitation has already been accepted.
            </CardDescription>
          </CardHeader>
          <CardContent className="text-center">
            <SuperButton onClick={() => navigate('/login')}>Go to Login</SuperButton>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (invitation.status === 'EXPIRED') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <Clock className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
            <CardTitle>Invitation Expired</CardTitle>
            <CardDescription>
              This invitation has expired. Please ask the team admin to send a new one.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (invitation.status === 'REVOKED') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <XCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
            <CardTitle>Invitation Revoked</CardTitle>
            <CardDescription>
              This invitation has been revoked by the team admin.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  if (accepted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
            <CardTitle>Welcome to the team!</CardTitle>
            <CardDescription>
              You have successfully joined the team. Redirecting...
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    )
  }

  // Existing user flow
  if (isAuthenticated && isExistingUser) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <Users className="h-12 w-12 text-primary mx-auto mb-4" />
            <CardTitle>Join Team</CardTitle>
            <CardDescription>
              You've been invited to join a team. Click below to accept the invitation.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {apiError.ErrorAlert}
            <div className="text-sm text-muted-foreground">
              <p>
                <strong>Invited email:</strong> {invitation.email}
              </p>
              {invitation.projectPermissions.length > 0 && (
                <p className="mt-2">
                  <strong>Project access:</strong>{' '}
                  {invitation.projectPermissions.length} project(s)
                </p>
              )}
            </div>
            <SuperButton className="w-full" onClick={handleAcceptForExistingUser}>
              Accept Invitation
            </SuperButton>
          </CardContent>
        </Card>
      </div>
    )
  }

  // New user flow - show signup form
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <Users className="h-12 w-12 text-primary mx-auto mb-4" />
          <CardTitle>Join Team</CardTitle>
          <CardDescription>
            Create an account to accept your invitation
          </CardDescription>
        </CardHeader>
        <CardContent>
          {apiError.ErrorAlert}
          <div className="mb-4 p-3 bg-muted rounded-md text-sm">
            <p>
              <strong>Email:</strong> {invitation.email}
            </p>
          </div>

          <SuperFormProvider
            config={{
              resolver: zodResolver(signupSchema),
              defaultValues: {
                firstName: '',
                lastName: '',
                password: '',
                confirmPassword: '',
              },
            }}
            apiError={apiError}
            onSubmit={handleAcceptForNewUser}
          >
            {(form) => (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <SuperField
                    label="First name"
                    name="firstName"
                    errorText={form.formState.errors.firstName?.message}
                  >
                    <Input {...form.register('firstName')} />
                  </SuperField>
                  <SuperField
                    label="Last name"
                    name="lastName"
                    errorText={form.formState.errors.lastName?.message}
                  >
                    <Input {...form.register('lastName')} />
                  </SuperField>
                </div>
                <SuperField
                  label="Password"
                  name="password"
                  errorText={form.formState.errors.password?.message}
                >
                  <Input type="password" {...form.register('password')} />
                </SuperField>
                <SuperField
                  label="Confirm password"
                  name="confirmPassword"
                  errorText={form.formState.errors.confirmPassword?.message}
                >
                  <Input type="password" {...form.register('confirmPassword')} />
                </SuperField>
                <SuperButton type="submit" className="w-full">
                  Create Account & Join Team
                </SuperButton>
              </div>
            )}
          </SuperFormProvider>
        </CardContent>
      </Card>
    </div>
  )
}
