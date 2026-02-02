import React, { useId } from 'react'
import { 
  Field, 
  FieldLabel, 
  FieldDescription, 
  FieldError,
  FieldContent 
} from '@/components/ui/field'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Info } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * SuperField - A comprehensive form field wrapper that handles labels, validation, and help text
 * 
 * Motivation:
 * - Provides consistent form field structure across the entire application
 * - Eliminates repetitive label, error, and helper text markup
 * - Ensures accessibility with proper ARIA attributes and associations
 * - Maintains visual consistency for required fields, errors, and help text
 * 
 * Features:
 * - Automatic label association with form controls
 * - Required field indicators (red asterisk)
 * - Helper text display (inline or as tooltip with info icon)
 * - Error message display with consistent styling
 * - Works with any form control (Input, Select, Textarea, etc.)
 * - Supports horizontal/vertical layouts via fieldProps
 * - Automatic ARIA attributes (aria-invalid, aria-describedby, aria-required)
 * - Unique ID generation for accessibility
 * 
 * @example
 * // Basic usage with validation
 * <SuperField 
 *   label="Email Address" 
 *   isRequired
 *   errorText={errors.email?.message}
 *   name="email"
 * >
 *   <Input {...register('email')} />
 * </SuperField>
 * 
 * @example
 * // With helper text as tooltip
 * <SuperField 
 *   label="Password"
 *   helperText="Must contain at least 8 characters"
 *   helperIcon
 *   name="password"
 * >
 *   <Input type="password" {...register('password')} />
 * </SuperField>
 */
export interface SuperFieldProps {
  label?: string | React.ReactNode
  labelProps?: React.ComponentPropsWithoutRef<typeof FieldLabel>
  helperText?: string
  children: React.ReactElement | null
  isRequired?: boolean
  isOptional?: boolean
  errorText?: string
  helperIcon?: boolean
  className?: string
  containerClassName?: string
  fieldProps?: React.ComponentPropsWithoutRef<typeof Field>
  name?: string // Added for proper form submission
}

export function SuperField({
  label,
  labelProps,
  helperText,
  errorText,
  children,
  isRequired,
  isOptional,
  helperIcon,
  className,
  containerClassName,
  fieldProps,
  name,
}: SuperFieldProps): React.ReactElement {
  // Generate unique IDs for accessibility
  const generatedId = useId()
  const fieldId = `field-${generatedId}`
  const errorId = `error-${generatedId}`
  const descriptionId = `description-${generatedId}`
  
  // Build aria-describedby value
  const ariaDescribedBy = [
    errorText && errorId,
    helperText && !helperIcon && !errorText && descriptionId,
  ].filter(Boolean).join(' ') || undefined

  // Clone child element and inject ARIA attributes
  const enhancedChild = children && React.cloneElement(children, {
    ...(children.props as any),
    id: (children.props as any)?.id || fieldId,
    name: (children.props as any)?.name || name,
    'aria-invalid': errorText ? 'true' : undefined,
    'aria-describedby': ariaDescribedBy || (children.props as any)?.['aria-describedby'],
    'aria-required': isRequired ? 'true' : undefined,
  } as any)

  return (
    <Field 
      {...fieldProps}
      className={cn(containerClassName, fieldProps?.className)}
      data-invalid={!!errorText}
    >
      {label && (
        <FieldLabel
          {...labelProps}
          htmlFor={fieldId}
          className={cn(labelProps?.className)}
        >
          {typeof label === 'string' ? (
            <span className="flex items-center gap-1">
              {label}
              {isRequired && (
                <span className="text-destructive" aria-label="required">
                  *
                </span>
              )}
              {isOptional && (
                <span className="text-muted-foreground text-sm" aria-label="optional">
                  (optional)
                </span>
              )}
              {helperIcon && helperText && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="inline-flex items-center cursor-help">
                        <Info className="h-3.5 w-3.5 text-muted-foreground" />
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p className="text-sm">{helperText}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </span>
          ) : (
            // When custom ReactNode is passed, user has full control - no automatic additions
            label
          )}
        </FieldLabel>
      )}
      
      <FieldContent className={className}>
        {enhancedChild}
        
        {helperText && !helperIcon && !errorText && (
          <FieldDescription id={descriptionId}>
            {helperText}
          </FieldDescription>
        )}
        
        {errorText && (
          <FieldError id={errorId}>
            {errorText}
          </FieldError>
        )}
      </FieldContent>
    </Field>
  )
}