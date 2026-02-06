import { useEffect, useRef, useState } from 'react'
import { cn } from '@/lib/utils'

interface FlipNumberProps {
  value: number
  formatter?: (n: number) => string
  className?: string
  duration?: number
}

export function FlipNumber({ value, formatter, className, duration = 500 }: FlipNumberProps) {
  const [displayValue, setDisplayValue] = useState(value)
  const prevValueRef = useRef(value)
  const animationRef = useRef<number | null>(null)

  useEffect(() => {
    const prevValue = prevValueRef.current

    // Skip animation if value hasn't changed
    if (prevValue === value) return

    // Cancel any existing animation
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current)
    }

    const startTime = performance.now()
    const startValue = prevValue

    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)

      // Ease-out cubic for smooth deceleration
      const eased = 1 - Math.pow(1 - progress, 3)
      const current = startValue + (value - startValue) * eased

      setDisplayValue(current)

      if (progress < 1) {
        animationRef.current = requestAnimationFrame(animate)
      } else {
        setDisplayValue(value)
        prevValueRef.current = value
      }
    }

    animationRef.current = requestAnimationFrame(animate)

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current)
      }
    }
  }, [value, duration])

  // Update ref when animation completes or on initial render
  useEffect(() => {
    prevValueRef.current = value
  }, [value])

  const formattedValue = formatter ? formatter(displayValue) : Math.round(displayValue).toString()

  return (
    <span className={cn("tabular-nums", className)}>
      {formattedValue}
    </span>
  )
}
