import React from 'react'
import { FormProvider, type UseFormProps, type FieldValues, type SubmitHandler } from 'react-hook-form'
import { useSuperForm } from '@/hooks/useSuperForm'

/**
 * SuperFormProvider - All-in-one form solution that combines useSuperForm, FormProvider, and form element
 * 
 * This component:
 * - Creates a form instance with useSuperForm (which includes accessibility features)
 * - Wraps children in FormProvider so SuperButton can access form state
 * - Renders a form element with proper submission handling
 * 
 * @example
 * <SuperFormProvider
 *   config={{
 *     resolver: zodResolver(schema),
 *     defaultValues: { email: '', password: '' }
 *   }}
 *   onSubmit={async (data) => {
 *     await login(data)
 *   }}
 * >
 *   {(form) => (
 *     <>
 *       <SuperField name="email" errorText={form.formState.errors.email?.message}>
 *         <Input {...form.register('email')} />
 *       </SuperField>
 *       <SuperButton type="submit">Submit</SuperButton>
 *     </>
 *   )}
 * </SuperFormProvider>
 */

interface ApiErrorHandler {
  setError: (error: unknown) => void
  clearError: () => void
  ErrorAlert: React.ReactNode
}

interface SuperFormProviderProps<TFieldValues extends FieldValues = FieldValues> 
  extends Omit<React.FormHTMLAttributes<HTMLFormElement>, 'onSubmit' | 'children'> {
  config: UseFormProps<TFieldValues>
  onSubmit: SubmitHandler<TFieldValues>
  apiError?: ApiErrorHandler
  children: (form: ReturnType<typeof useSuperForm<TFieldValues>>) => React.ReactNode
}

export function SuperFormProvider<TFieldValues extends FieldValues = FieldValues>({
  config,
  onSubmit,
  apiError,
  children,
  ...formProps
}: SuperFormProviderProps<TFieldValues>) {
  const form = useSuperForm<TFieldValues>(config)
  
  // Wrap onSubmit to handle error clearing and catching
  const handleSubmit = async (data: TFieldValues) => {
    try {
      // Clear any existing errors when starting submission
      apiError?.clearError()
      
      // Call the provided onSubmit
      await onSubmit(data)
    } catch (error) {
      // If apiError handler is provided, use it to handle the error
      if (apiError) {
        apiError.setError(error)
      } else {
        // Re-throw if no error handler provided (backwards compatibility)
        throw error
      }
    }
  }
  
  return (
    <FormProvider {...form}>
      <form onSubmit={form.handleSubmit(handleSubmit)} {...formProps}>
        {children(form)}
      </form>
    </FormProvider>
  )
}