import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface FlipDigitProps {
  digit: string
  delay: number
}

function FlipDigit({ digit, delay }: FlipDigitProps) {
  const [currentDigit, setCurrentDigit] = useState(digit)
  const [previousDigit, setPreviousDigit] = useState(digit)
  const [isFlipping, setIsFlipping] = useState(false)

  useEffect(() => {
    if (digit !== currentDigit) {
      setPreviousDigit(currentDigit)
      setIsFlipping(true)

      const timer = setTimeout(() => {
        setCurrentDigit(digit)
        setIsFlipping(false)
      }, 300) // Match animation duration

      return () => clearTimeout(timer)
    }
  }, [digit, currentDigit])

  // Initial animation on mount
  const [hasAnimated, setHasAnimated] = useState(false)
  useEffect(() => {
    const timer = setTimeout(() => {
      setHasAnimated(true)
    }, delay)
    return () => clearTimeout(timer)
  }, [delay])

  return (
    <span
      className={cn(
        "inline-block relative overflow-hidden",
        "w-[0.6em] h-[1.2em]",
        digit === ',' || digit === '.' || digit === '$' || digit === 'K' || digit === 'M' || digit === '%'
          ? "w-[0.4em]"
          : ""
      )}
    >
      {/* Static background digit (shows briefly during flip) */}
      <span
        className="absolute inset-0 flex items-center justify-center text-inherit"
        aria-hidden="true"
      >
        {previousDigit}
      </span>

      {/* Animated digit */}
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center text-inherit",
          "transition-transform duration-300 ease-out",
          !hasAnimated && "translate-y-full opacity-0",
          hasAnimated && !isFlipping && "translate-y-0 opacity-100",
          isFlipping && "-translate-y-full opacity-0"
        )}
        style={{ transitionDelay: hasAnimated ? '0ms' : `${delay}ms` }}
      >
        {currentDigit}
      </span>

      {/* New digit flipping in */}
      {isFlipping && (
        <span
          className={cn(
            "absolute inset-0 flex items-center justify-center text-inherit",
            "animate-flip-in"
          )}
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
  const prevValueRef = useRef(formattedValue)

  // Pad shorter strings to match length for smooth transitions
  const maxLen = Math.max(formattedValue.length, prevValueRef.current.length)
  const paddedCurrent = formattedValue.padStart(maxLen, ' ')
  const digits = paddedCurrent.split('')

  useEffect(() => {
    prevValueRef.current = formattedValue
  }, [formattedValue])

  return (
    <span className={cn("inline-flex tabular-nums", className)}>
      {digits.map((digit, i) => (
        <FlipDigit
          key={`${i}-${digits.length}`}
          digit={digit}
          delay={i * 50} // Stagger animation
        />
      ))}
    </span>
  )
}
