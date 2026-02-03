import { Navigate, useNavigate } from 'react-router'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { SuperButton } from '@/components/SuperButton'
import { SuperField } from '@/components/SuperField'
import { SuperFormProvider } from '@/components/SuperFormProvider'
import { Input } from '@/components/ui/input'
import { useApiError } from '@/hooks/useApiError'
import { useCreateCustomer } from '@/generated/authorization/authorization'
import { useAuth } from '@/contexts/AuthContext'

const createTeamSchema = z.object({
  name: z.string().min(1, 'Team name is required').trim(),
})

type CreateTeamFormValues = z.infer<typeof createTeamSchema>

export function CreateTeamPage() {
  const navigate = useNavigate()
  const apiError = useApiError()
  const { isAuthenticated, isLoading } = useAuth()
  const createCustomerMutation = useCreateCustomer()

  const formConfig = {
    resolver: zodResolver(createTeamSchema),
    defaultValues: {
      name: '',
    },
  }

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900"></div>
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  const onSubmit = async (data: CreateTeamFormValues) => {
    await createCustomerMutation.mutateAsync({
      data: {
        name: data.name,
      },
    })

    // Navigate to projects and reload to refresh auth context
    navigate('/')
    window.location.reload()
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-full max-w-md space-y-8 p-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold">Create your team</h2>
          <p className="mt-2 text-gray-600">
            Start tracking your team's Claude Code token usage
          </p>
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
                <SuperField
                  label="Team name"
                  name="name"
                  helperText="This will be the name of your workspace"
                  errorText={form.formState.errors.name?.message}
                >
                  <Input
                    type="text"
                    placeholder="My Team"
                    {...form.register('name')}
                    autoFocus
                  />
                </SuperField>
              </div>

              <div className="space-y-3">
                <SuperButton
                  type="submit"
                  className="w-full"
                >
                  Create team
                </SuperButton>
              </div>
            </>
          )}
        </SuperFormProvider>
      </div>
    </div>
  )
}
