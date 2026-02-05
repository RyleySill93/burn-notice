import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface FlipDigitProps {
  digit: string
  delay: number
}

function FlipDigit({ digit, delay }: FlipDigitProps) {
  const [displayDigit, setDisplayDigit] = useState(digit)
  const [isAnimating, setIsAnimating] = useState(false)
  const [hasInitialized, setHasInitialized] = useState(false)
  const prevDigitRef = useRef(digit)

  // Handle initial mount animation
  useEffect(() => {
    const timer = setTimeout(() => {
      setHasInitialized(true)
    }, delay)
    return () => clearTimeout(timer)
  }, [delay])

  // Handle digit changes after initialization
  useEffect(() => {
    if (hasInitialized && digit !== prevDigitRef.current) {
      setIsAnimating(true)
      const timer = setTimeout(() => {
        setDisplayDigit(digit)
        setIsAnimating(false)
        prevDigitRef.current = digit
      }, 150)
      return () => clearTimeout(timer)
    }
  }, [digit, hasInitialized])

  // Sync display digit when it changes externally during initial render
  useEffect(() => {
    if (!hasInitialized) {
      setDisplayDigit(digit)
      prevDigitRef.current = digit
    }
  }, [digit, hasInitialized])

  const isSymbol = digit === ',' || digit === '.' || digit === '$' || digit === 'K' || digit === 'M' || digit === '%'

  return (
    <span
      className={cn(
        "inline-block relative overflow-hidden",
        "h-[1.2em]",
        isSymbol ? "w-[0.35em]" : "w-[0.6em]"
      )}
    >
      {/* Current digit */}
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center text-inherit transition-all duration-150 ease-out",
          !hasInitialized && "translate-y-full opacity-0",
          hasInitialized && !isAnimating && "translate-y-0 opacity-100",
          isAnimating && "-translate-y-full opacity-0"
        )}
      >
        {displayDigit}
      </span>

      {/* New digit sliding in */}
      {isAnimating && (
        <span
          className="absolute inset-0 flex items-center justify-center text-inherit animate-flip-in"
        >
          {digit}
        </span>
      )}
    </span>
  )
}

interface FlipNumberProps {
  value: number
  formatter?: (n: number) => string
  className?: string
}

export function FlipNumber({ value, formatter, className }: FlipNumberProps) {
  const formattedValue = formatter ? formatter(value) : value.toString()
  const prevLengthRef = useRef(formattedValue.length)

  // Pad to maintain consistent width during transitions
  const maxLen = Math.max(formattedValue.length, prevLengthRef.current)
  const paddedValue = formattedValue.padStart(maxLen, ' ')
  const digits = paddedValue.split('')

  useEffect(() => {
    prevLengthRef.current = formattedValue.length
  }, [formattedValue])

  return (
    <span className={cn("inline-flex tabular-nums", className)}>
      {digits.map((digit, i) => (
        <FlipDigit
          key={`${i}-${maxLen}`}
          digit={digit}
          delay={i * 30}
        />
      ))}
    </span>
  )
}
