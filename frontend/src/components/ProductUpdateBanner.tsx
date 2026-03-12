import { useState, useEffect, useRef } from 'react'
import { Timer, X } from 'lucide-react'

const STORAGE_KEY = 'burn-notice-dismissed-time-burned-banner'

interface ProductUpdateBannerProps {
  onFirstShow?: () => void
}

export function ProductUpdateBanner({ onFirstShow }: ProductUpdateBannerProps) {
  const [isDismissed, setIsDismissed] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) === 'true'
  })
  const onFirstShowCalled = useRef(false)

  useEffect(() => {
    if (!isDismissed && !onFirstShowCalled.current && onFirstShow) {
      onFirstShowCalled.current = true
      onFirstShow()
    }
  }, [isDismissed, onFirstShow])

  if (isDismissed) {
    return null
  }

  const handleDismiss = () => {
    localStorage.setItem(STORAGE_KEY, 'true')
    setIsDismissed(true)
  }

  return (
    <div className="relative flex items-center gap-3 rounded-lg border border-orange-200 bg-gradient-to-r from-orange-50 to-amber-50 px-4 py-2.5 text-sm text-orange-900">
      <Timer className="h-4 w-4 shrink-0 text-orange-500" />
      <span>
        <span className="font-semibold">New: Time Burned metric</span>
        {' '}&mdash; See how many hours your team actively burns tokens each day.
      </span>
      <button
        onClick={handleDismiss}
        className="ml-auto shrink-0 rounded-md p-1 text-orange-400 transition-colors hover:bg-orange-100 hover:text-orange-600"
        aria-label="Dismiss banner"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
