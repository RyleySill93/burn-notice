import { useId } from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

// --- Glyphs ---

export function FlameGlyph() {
  return (
    <g>
      <path
        d="M28 13.2c1.9 2.2 3 4.2 3.3 6.1.4 2.2-.1 4-1 5.7 2.2-1 4-2.9 4.9-5.7 1.8 2.2 2.8 4.8 2.8 7.6 0 5.7-4.4 10-10 10s-10-4.3-10-10c0-4.2 2.1-7.6 5.7-10.6 2.4-2 3.8-4.1 3.9-6.7 0-.5.8-.7 1.1-.4.1.1.2.3.3.4Z"
        fill="rgba(255,255,255,0.98)"
      />
      <path
        d="M28.1 19.5c.8 1.3 1.2 2.5 1.3 3.6.2 1.2-.1 2.3-.7 3.3 1.4-.6 2.4-1.8 3-3.5 1.2 1.4 1.9 3 1.9 4.9 0 3.8-2.5 6.4-5.8 6.4-3.5 0-5.9-2.6-5.9-6.2 0-2.8 1.5-5 4-7 .9-.7 1.6-1.7 1.8-2.9 0-.4.3-.4.4-.2Z"
        fill="rgba(0,0,0,0.18)"
      />
      <path
        d="M29.2 16.2c1.3 1.7 2 3.4 2.2 5.2"
        fill="none"
        stroke="rgba(255,255,255,0.32)"
        strokeWidth="1.2"
        strokeLinecap="round"
      />
      <path
        d="M22.2 31.8c.7 1.8 2 3.1 3.8 3.9"
        fill="none"
        stroke="rgba(255,255,255,0.18)"
        strokeWidth="1.1"
        strokeLinecap="round"
      />
    </g>
  )
}

export function TimeGlyph() {
  return (
    <g>
      <circle cx="28" cy="25" r="9" fill="none" stroke="rgba(255,255,255,0.95)" strokeWidth="2.2" />
      <path
        d="M28 25L28 20.3M28 25L32.4 27.2"
        stroke="rgba(255,255,255,0.95)"
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      <path d="M24 12.8h8" stroke="rgba(255,255,255,0.6)" strokeWidth="1.8" strokeLinecap="round" />
      <path
        d="M20.7 15.2l-1.8 1.6M35.3 15.2l1.8 1.6"
        stroke="rgba(255,255,255,0.6)"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </g>
  )
}

// --- Shared Primitives ---

export function ShineSweep({ id, delay = 0 }: { id: string; delay?: number }) {
  return (
    <motion.g
      animate={{ x: [-36, 72], opacity: [0, 0.26, 0] }}
      transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut', delay, repeatDelay: 1.2 }}
    >
      <defs>
        <linearGradient id={`${id}-sweep`} x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="rgba(255,255,255,0)" />
          <stop offset="50%" stopColor="rgba(255,255,255,0.95)" />
          <stop offset="100%" stopColor="rgba(255,255,255,0)" />
        </linearGradient>
      </defs>
      <rect
        x="0"
        y="0"
        width="10"
        height="56"
        rx="5"
        fill={`url(#${id}-sweep)`}
        transform="rotate(18 5 28)"
      />
    </motion.g>
  )
}

export function CountChip({ count }: { count: number }) {
  const text = count > 99 ? '99+' : `${count}`
  return (
    <g>
      <rect x="15.5" y="34.5" width="25" height="13" rx="6.5" fill="rgba(0,0,0,0.6)" stroke="rgba(255,255,255,0.15)" />
      <text
        x="28"
        y="43.4"
        textAnchor="middle"
        fontSize="8.5"
        fontWeight="800"
        fill="#fff"
        style={{ letterSpacing: '0.04em' }}
      >
        x{text}
      </text>
    </g>
  )
}

export function WeeklyMark() {
  return (
    <g opacity="0.95">
      <rect x="7" y="9" width="11" height="2.5" rx="1.25" fill="rgba(255,255,255,0.92)" />
      <rect x="7" y="13" width="7" height="2.5" rx="1.25" fill="rgba(255,255,255,0.45)" />
    </g>
  )
}

// --- Badge Frame Wrapper ---

export function BadgeFrame({
  children,
  size = 56,
  className,
  glowColor,
  glowShape = 'rounded-full',
}: {
  children: React.ReactNode
  size?: number
  className?: string
  glowColor: string
  glowShape?: string
}) {
  return (
    <motion.div
      whileHover={{ scale: 1.12, rotate: -3, y: -3 }}
      whileTap={{ scale: 0.95 }}
      transition={{ type: 'spring', stiffness: 400, damping: 15 }}
      className={cn('relative inline-flex items-center justify-center cursor-pointer select-none', className)}
      style={{ width: size, height: size }}
    >
      <motion.div
        className={cn('absolute inset-0', glowShape)}
        animate={{ opacity: [0.18, 0.34, 0.18], scale: [0.96, 1.05, 0.96] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        style={{ background: glowColor }}
      />
      {children}
    </motion.div>
  )
}

export function useBadgeId(prefix: string) {
  const raw = useId()
  return `${prefix}-${raw.replace(/:/g, '')}`
}
