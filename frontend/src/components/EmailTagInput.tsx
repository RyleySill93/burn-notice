import { useState, useRef, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface EmailTagInputProps {
  value: string[]
  onChange: (emails: string[]) => void
  placeholder?: string
  className?: string
  disabled?: boolean
}

export function EmailTagInput({
  value,
  onChange,
  placeholder = 'Enter email addresses',
  className,
  disabled,
}: EmailTagInputProps) {
  const [inputValue, setInputValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const isValidEmail = (email: string): boolean => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
  }

  const addEmail = (email: string) => {
    const trimmed = email.trim().toLowerCase()
    if (trimmed && isValidEmail(trimmed) && !value.includes(trimmed)) {
      onChange([...value, trimmed])
      setInputValue('')
    }
  }

  const removeEmail = (emailToRemove: string) => {
    onChange(value.filter((email) => email !== emailToRemove))
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
      e.preventDefault()
      addEmail(inputValue)
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      removeEmail(value[value.length - 1])
    }
  }

  const handleBlur = () => {
    if (inputValue) {
      addEmail(inputValue)
    }
  }

  return (
    <div
      className={cn(
        'flex flex-wrap gap-2 p-2 min-h-[80px] border rounded-md bg-background focus-within:ring-2 focus-within:ring-ring cursor-text',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={() => inputRef.current?.focus()}
    >
      {value.map((email) => (
        <Badge key={email} variant="secondary" className="gap-1 h-7">
          {email}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              removeEmail(email)
            }}
            className="ml-1 hover:text-destructive"
            disabled={disabled}
          >
            <X className="h-3 w-3" />
          </button>
        </Badge>
      ))}
      <Input
        ref={inputRef}
        type="email"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        placeholder={value.length === 0 ? placeholder : ''}
        disabled={disabled}
        className="flex-1 min-w-[200px] border-0 p-0 h-7 focus-visible:ring-0 shadow-none"
      />
    </div>
  )
}
