import { forwardRef, useState } from 'react'
import { useFormContext } from 'react-hook-form'
import { Button, buttonVariants } from '@/components/ui/button'
import { Loader2, type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { type VariantProps } from 'class-variance-authority'

/**
 * SuperButton - An enhanced button component that automatically handles loading states
 * 
 * Motivation:
 * - Eliminates boilerplate for managing loading states in buttons
 * - Prevents double-clicks automatically during async operations
 * - Provides consistent UX with loading spinners for all async actions
 * - Supports icon placement for better visual hierarchy
 * 
 * Features:
 * - Automatically detects when onClick returns a Promise and shows loading state
 * - Displays a spinner icon during loading, replacing any left icon
 * - Disables the button during loading to prevent multiple submissions
 * - Supports optional left and right icons for non-loading states
 * - Preserves all standard Button props (variant, size, className, etc.)
 * 
 * @example
 * // Simple async button
 * <SuperButton onClick={async () => await saveData()}>
 *   Save
 * </SuperButton>
 * 
 * @example
 * // With icons
 * <SuperButton 
 *   leftIcon={Save}
 *   rightIcon={ArrowRight}
 *   onClick={handleSubmit}
 * >
 *   Save and Continue
 * </SuperButton>
 */
export interface SuperButtonProps extends React.ComponentProps<'button'>, VariantProps<typeof buttonVariants> {
  leftIcon?: LucideIcon
  rightIcon?: LucideIcon
  onClick?: (event: React.MouseEvent<HTMLButtonElement>) => void | Promise<void>
  asChild?: boolean
}

export const SuperButton = forwardRef<HTMLButtonElement, SuperButtonProps>(
  ({ leftIcon: LeftIcon, rightIcon: RightIcon, onClick, children, disabled, className, type, ...props }, ref) => {
    const [isAsyncLoading, setIsAsyncLoading] = useState(false)
    
    // Try to get form context if we're inside a React Hook Form
    const formContext = useFormContext()
    const isFormSubmitting = formContext?.formState?.isSubmitting ?? false
    
    // Use form submission state for submit buttons, async state for onClick promises
    const isLoading = (type === 'submit' && isFormSubmitting) || isAsyncLoading

    const handleClick = async (event: React.MouseEvent<HTMLButtonElement>) => {
      if (!onClick || isAsyncLoading) return

      const result = onClick(event)
      
      // Check if the onClick returns a promise
      if (result instanceof Promise) {
        setIsAsyncLoading(true)
        try {
          await result
        } catch (error) {
          // Let the onClick handle its own errors
          console.error('Button promise rejected:', error)
        } finally {
          setIsAsyncLoading(false)
        }
      }
    }

    // Determine which icon to show on the left
    const ActualLeftIcon = isLoading ? Loader2 : LeftIcon

    return (
      <Button
        ref={ref}
        onClick={handleClick}
        disabled={disabled || isLoading}
        className={cn("cursor-pointer", className)}
        {...props}
      >
        {ActualLeftIcon && (
          <ActualLeftIcon 
            className={cn(
              "h-4 w-4",
              children && "mr-2",
              isLoading && "animate-spin"
            )} 
          />
        )}
        {children}
        {RightIcon && !isLoading && (
          <RightIcon 
            className={cn(
              "h-4 w-4",
              children && "ml-2"
            )} 
          />
        )}
      </Button>
    )
  }
)

SuperButton.displayName = 'SuperButton'