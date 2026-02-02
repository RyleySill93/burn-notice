import { useForm as useRHF, type UseFormProps, type UseFormReturn, type FieldValues, type SubmitHandler, type SubmitErrorHandler } from 'react-hook-form'
import { useCallback, useEffect, useRef } from 'react'

/**
 * useSuperForm - Enhanced React Hook Form with automatic accessibility features
 * 
 * Features:
 * - Automatically focuses first error field on validation failure
 * - Announces form errors to screen readers
 * - Preserves all React Hook Form functionality
 * - Zero configuration required
 * 
 * @example
 * const form = useSuperForm({
 *   resolver: zodResolver(schema),
 *   defaultValues: { email: '', password: '' }
 * })
 * 
 * // Use exactly like regular useForm
 * <form onSubmit={form.handleSubmit(onSubmit)}>
 */
export function useSuperForm<TFieldValues extends FieldValues = FieldValues>(
  props?: UseFormProps<TFieldValues>
): UseFormReturn<TFieldValues> {
  // Use onSubmit mode to prevent automatic validation, we'll trigger it manually
  const formProps = {
    mode: 'onSubmit' as const,
    reValidateMode: 'onChange' as const,
    delayError: 200, // 200ms delay prevents validation from blocking link clicks
    ...props,
  }
  
  const form = useRHF<TFieldValues>(formProps)
  const { formState: { errors, isSubmitted, isDirty }, setFocus, trigger } = form
  
  // Store the original register function before overriding
  const originalRegisterRef = useRef(form.register)
  
  // Override register to control validation behavior
  form.register = useCallback((name, options) => {
    const registration = originalRegisterRef.current(name, options)
    
    return {
      ...registration,
      onChange: async (e) => {
        // Call original onChange to update form state
        await registration.onChange(e)
        
        // After form submission, validate on change
        if (isSubmitted) {
          await trigger(name)
        }
      },
      onBlur: async (e) => {
        // Call original onBlur
        if (registration.onBlur) {
          await registration.onBlur(e)
        }
        
        // Before submission: only validate on blur if form is dirty
        // After submission: validation already happens onChange
        if (!isSubmitted && isDirty) {
          await trigger(name)
        }
      },
    }
  }, [trigger, isSubmitted, isDirty])

  // Auto-focus first field on mount
  useEffect(() => {
    // Find the first input, textarea, or select in the form
    const timer = setTimeout(() => {
      const firstField = document.querySelector<HTMLElement>(
        'form input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([disabled]), ' +
        'form textarea:not([disabled]), ' +
        'form select:not([disabled])'
      )
      if (firstField && document.activeElement === document.body) {
        firstField.focus()
      }
    }, 0)
    
    return () => clearTimeout(timer)
  }, [])

  // Focus first error field after form submission attempt
  useEffect(() => {
    if (isSubmitted && Object.keys(errors).length > 0) {
      const firstErrorField = Object.keys(errors)[0] as any
      // Small timeout to ensure DOM has updated with error states
      setTimeout(() => {
        setFocus(firstErrorField)
        
        // Announce to screen readers
        const errorCount = Object.keys(errors).length
        const announcement = `Form validation failed. ${errorCount} ${errorCount === 1 ? 'error' : 'errors'} found. Please review the highlighted fields.`
        
        // Create or update aria-live region for announcements
        let liveRegion = document.getElementById('form-error-announcement')
        if (!liveRegion) {
          liveRegion = document.createElement('div')
          liveRegion.id = 'form-error-announcement'
          liveRegion.setAttribute('aria-live', 'assertive')
          liveRegion.setAttribute('aria-atomic', 'true')
          liveRegion.className = 'sr-only' // Visually hidden but available to screen readers
          document.body.appendChild(liveRegion)
        }
        liveRegion.textContent = announcement
        
        // Clear announcement after 1 second to prepare for next announcement
        setTimeout(() => {
          if (liveRegion) {
            liveRegion.textContent = ''
          }
        }, 1000)
      }, 100)
    }
  }, [isSubmitted, errors, setFocus])

  // Enhanced handleSubmit that includes focus management
  const handleSubmit = useCallback(
    (onValid: SubmitHandler<TFieldValues>, onInvalid?: SubmitErrorHandler<TFieldValues>) => {
      return form.handleSubmit(
        onValid,
        onInvalid || ((errors) => {
          // Default error handler if none provided
          console.log('Form validation errors:', errors)
        })
      )
    },
    [form]
  )

  return {
    ...form,
    handleSubmit,
  }
}