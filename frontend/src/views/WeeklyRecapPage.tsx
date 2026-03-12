import { useState, useEffect, useCallback } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { Flame, Trophy, Clock, Zap, ChevronLeft, ChevronRight, Crown, Medal, Award, Calendar } from 'lucide-react'
import { addDays, subDays, startOfWeek } from 'date-fns'
import { motion, AnimatePresence } from 'framer-motion'
import confetti from 'canvas-confetti'
import axios from '@/lib/axios-instance'
import { format } from 'date-fns'

interface PodiumEntry {
  engineerId: string
  displayName: string
  rank: number
  value: number
}

interface RecapRecord {
  engineerId: string
  displayName: string
  recordType: string
  recordPeriod: string
  recordScope: string
  value: number
  previousValue: number | null
  recordDate: string
}

interface WeeklyRecapData {
  weekStart: string
  weekEnd: string
  tokensPodium: PodiumEntry[]
  timePodium: PodiumEntry[]
  records: RecapRecord[]
  teamTotalTokens: number
  teamTotalMinutes: number
}

const FLAME_WAR_USER_IDS = ['user-6yckeUKu1M9nH', 'user-pxSgASZi41Zq']

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return n.toLocaleString()
}

function formatMinutes(mins: number): string {
  const hours = Math.floor(mins / 60)
  const remaining = Math.round(mins % 60)
  if (hours === 0) return `${remaining}m`
  return `${hours}h ${remaining}m`
}

function fireConfetti() {
  const duration = 3000
  const end = Date.now() + duration

  const frame = () => {
    confetti({
      particleCount: 3,
      angle: 60,
      spread: 55,
      origin: { x: 0, y: 0.7 },
      colors: ['#f97316', '#ef4444', '#eab308', '#f59e0b'],
    })
    confetti({
      particleCount: 3,
      angle: 120,
      spread: 55,
      origin: { x: 1, y: 0.7 },
      colors: ['#f97316', '#ef4444', '#eab308', '#f59e0b'],
    })

    if (Date.now() < end) {
      requestAnimationFrame(frame)
    }
  }
  frame()
}

function fireBigConfetti() {
  confetti({
    particleCount: 150,
    spread: 100,
    origin: { y: 0.6 },
    colors: ['#f97316', '#ef4444', '#eab308', '#f59e0b', '#ffffff'],
  })
}

// --- Slide Components ---

function TitleSlide({ weekStart, weekEnd }: { weekStart: string; weekEnd: string }) {
  useEffect(() => {
    const timer = setTimeout(fireConfetti, 500)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8">
      <motion.div
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: 'spring', duration: 1, bounce: 0.5 }}
      >
        <Flame className="h-32 w-32 text-orange-500" />
      </motion.div>
      <motion.h1
        initial={{ opacity: 0, y: 50 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5, duration: 0.8 }}
        className="text-7xl font-bold text-center"
        style={{ fontFamily: 'Bangers, cursive' }}
      >
        Weekly Burn Report
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.5 }}
        className="text-2xl text-muted-foreground"
      >
        {format(new Date(weekStart), 'MMM d')} - {format(new Date(weekEnd), 'MMM d, yyyy')}
      </motion.p>
    </div>
  )
}

function TeamTotalsSlide({ tokens, minutes }: { tokens: number; minutes: number }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-12">
      <motion.h2
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="text-5xl font-bold"
        style={{ fontFamily: 'Bangers, cursive' }}
      >
        This Week the Team...
      </motion.h2>
      <div className="flex gap-16">
        <motion.div
          initial={{ opacity: 0, x: -100 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.4, type: 'spring', bounce: 0.4 }}
          className="flex flex-col items-center gap-4 bg-gradient-to-b from-orange-500/20 to-transparent rounded-2xl p-10 border border-orange-500/30"
        >
          <Zap className="h-16 w-16 text-orange-400" />
          <CountUp end={tokens} duration={2000} className="text-6xl font-bold text-orange-400" format={formatNumber} />
          <span className="text-xl text-muted-foreground">tokens burned</span>
        </motion.div>
        <motion.div
          initial={{ opacity: 0, x: 100 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6, type: 'spring', bounce: 0.4 }}
          className="flex flex-col items-center gap-4 bg-gradient-to-b from-red-500/20 to-transparent rounded-2xl p-10 border border-red-500/30"
        >
          <Clock className="h-16 w-16 text-red-400" />
          <CountUp end={minutes} duration={2000} className="text-6xl font-bold text-red-400" format={formatMinutes} />
          <span className="text-xl text-muted-foreground">time burned</span>
        </motion.div>
      </div>
    </div>
  )
}

function PodiumSlide({
  title,
  icon: Icon,
  podium,
  formatValue,
  color,
}: {
  title: string
  icon: typeof Trophy
  podium: PodiumEntry[]
  formatValue: (v: number) => string
  color: string
}) {
  useEffect(() => {
    const timer = setTimeout(fireBigConfetti, 1200)
    return () => clearTimeout(timer)
  }, [])

  const podiumOrder = [1, 0, 2] // 2nd, 1st, 3rd for visual layout
  const podiumHeights = ['h-40', 'h-56', 'h-32']
  const podiumColors = [
    'from-gray-400/30 border-gray-400/50',
    'from-yellow-500/30 border-yellow-500/50',
    'from-amber-700/30 border-amber-700/50',
  ]
  const rankIcons = [
    <Medal key="silver" className="h-10 w-10 text-gray-400" />,
    <Crown key="gold" className="h-12 w-12 text-yellow-400" />,
    <Award key="bronze" className="h-8 w-8 text-amber-700" />,
  ]
  const delays = [0.6, 0.3, 0.9]

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8">
      <motion.div
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4"
      >
        <Icon className={`h-12 w-12 ${color}`} />
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          {title}
        </h2>
      </motion.div>
      <div className="flex items-end gap-6 mt-8">
        {podiumOrder.map((idx, visualIdx) => {
          const entry = podium[idx]
          if (!entry) return null
          return (
            <motion.div
              key={entry.engineerId}
              initial={{ opacity: 0, y: 100 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: delays[visualIdx], type: 'spring', bounce: 0.3 }}
              className="flex flex-col items-center gap-3"
            >
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: delays[visualIdx] + 0.3, type: 'spring' }}
              >
                {rankIcons[visualIdx]}
              </motion.div>
              <span className="text-xl font-semibold truncate max-w-[180px]">{entry.displayName}</span>
              <span className={`text-2xl font-bold ${color}`}>{formatValue(entry.value)}</span>
              <div
                className={`w-44 ${podiumHeights[visualIdx]} rounded-t-xl bg-gradient-to-t ${podiumColors[visualIdx]} border border-b-0 flex items-center justify-center`}
              >
                <span className="text-4xl font-bold opacity-30" style={{ fontFamily: 'Bangers, cursive' }}>
                  #{entry.rank}
                </span>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function RecordsSlide({ records }: { records: RecapRecord[] }) {
  useEffect(() => {
    if (records.length > 0) {
      const timer = setTimeout(fireConfetti, 500)
      return () => clearTimeout(timer)
    }
  }, [records.length])

  const companyRecords = records.filter((r) => r.recordScope === 'company')
  const personalRecords = records.filter((r) => r.recordScope === 'personal')

  if (records.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-8">
        <motion.h2
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="text-5xl font-bold"
          style={{ fontFamily: 'Bangers, cursive' }}
        >
          No Records Broken
        </motion.h2>
        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.3 }}
          className="text-2xl text-muted-foreground"
        >
          The records stand... for now.
        </motion.p>
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8 px-8">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4">
        <Trophy className="h-12 w-12 text-yellow-400" />
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          Records Broken!
        </h2>
      </motion.div>
      <div className="flex gap-12 w-full max-w-5xl">
        {companyRecords.length > 0 && (
          <motion.div
            initial={{ opacity: 0, x: -50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="flex-1"
          >
            <h3 className="text-2xl font-bold text-center mb-4 text-yellow-400" style={{ fontFamily: 'Bangers, cursive' }}>
              Company Records
            </h3>
            <div className="space-y-3">
              {companyRecords.map((r, i) => (
                <RecordCard key={i} record={r} delay={0.4 + i * 0.15} />
              ))}
            </div>
          </motion.div>
        )}
        {personalRecords.length > 0 && (
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.5 }}
            className="flex-1"
          >
            <h3 className="text-2xl font-bold text-center mb-4 text-orange-400" style={{ fontFamily: 'Bangers, cursive' }}>
              Personal Records
            </h3>
            <div className="space-y-3">
              {personalRecords.map((r, i) => (
                <RecordCard key={i} record={r} delay={0.6 + i * 0.15} />
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

function RecordCard({ record, delay }: { record: RecapRecord; delay: number }) {
  const isTokens = record.recordType === 'tokens'
  const icon = isTokens ? <Zap className="h-5 w-5 text-orange-400" /> : <Clock className="h-5 w-5 text-red-400" />
  const valueStr = isTokens ? formatNumber(record.value) : formatMinutes(record.value)
  const prevStr = record.previousValue
    ? isTokens
      ? formatNumber(record.previousValue)
      : formatMinutes(record.previousValue)
    : null
  const periodLabel = record.recordPeriod === 'daily' ? 'Daily' : record.recordPeriod === 'weekly' ? 'Weekly' : 'Monthly'
  const typeLabel = isTokens ? 'Tokens' : 'Time'

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, type: 'spring' }}
      className="flex items-center gap-4 bg-card border border-border rounded-xl p-4"
    >
      {icon}
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold">{record.displayName}</span>
          <span className="text-xs bg-orange-500/20 text-orange-400 px-2 py-0.5 rounded-full">
            {periodLabel} {typeLabel}
          </span>
        </div>
        <div className="text-sm text-muted-foreground">
          <span className="text-foreground font-bold">{valueStr}</span>
          {prevStr && (
            <span>
              {' '}
              (was {prevStr})
            </span>
          )}
        </div>
      </div>
    </motion.div>
  )
}

function OutroSlide() {
  useEffect(() => {
    const timer = setTimeout(fireConfetti, 300)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center h-full gap-8">
      <motion.div
        initial={{ scale: 0, rotate: -180 }}
        animate={{ scale: 1, rotate: 0 }}
        transition={{ type: 'spring', duration: 1.2, bounce: 0.5 }}
      >
        <Flame className="h-40 w-40 text-orange-500" />
      </motion.div>
      <motion.h1
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
        className="text-6xl font-bold text-center"
        style={{ fontFamily: 'Bangers, cursive' }}
      >
        Keep Burning!
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1 }}
        className="text-xl text-muted-foreground"
      >
        See you next week.
      </motion.p>
    </div>
  )
}

// --- Utilities ---

function CountUp({
  end,
  duration,
  className,
  format: fmt,
}: {
  end: number
  duration: number
  className: string
  format: (n: number) => string
}) {
  const [value, setValue] = useState(0)

  useEffect(() => {
    const startTime = Date.now()
    const timer = setInterval(() => {
      const elapsed = Date.now() - startTime
      const progress = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      setValue(Math.round(end * eased))
      if (progress >= 1) clearInterval(timer)
    }, 16)
    return () => clearInterval(timer)
  }, [end, duration])

  return <span className={className}>{fmt(value)}</span>
}

// --- Main Component ---

function WeeklyRecapContent() {
  const navigate = useNavigate()
  const [currentSlide, setCurrentSlide] = useState(0)
  const [asOfDate, setAsOfDate] = useState<Date>(new Date())

  const isCurrentWeek = startOfWeek(asOfDate, { weekStartsOn: 1 }).getTime() ===
    startOfWeek(new Date(), { weekStartsOn: 1 }).getTime()

  const goToPrevWeek = useCallback(() => {
    setAsOfDate((prev) => subDays(prev, 7))
    setCurrentSlide(0)
  }, [])

  const goToNextWeek = useCallback(() => {
    setAsOfDate((prev) => {
      const next = addDays(prev, 7)
      return next > new Date() ? new Date() : next
    })
    setCurrentSlide(0)
  }, [])

  const asOfStr = format(asOfDate, 'yyyy-MM-dd')

  const { data, isFetching } = useQuery<WeeklyRecapData>({
    queryKey: ['weekly-recap', asOfStr],
    queryFn: async () => {
      const response = await axios.get<WeeklyRecapData>('/api/leaderboard/weekly-recap', {
        params: { as_of: asOfStr },
      })
      return response.data
    },
  })

  const totalSlides = 6 // title, totals, tokens podium, time podium, records, outro

  const goNext = useCallback(() => {
    setCurrentSlide((prev) => Math.min(prev + 1, totalSlides - 1))
  }, [totalSlides])

  const goPrev = useCallback(() => {
    setCurrentSlide((prev) => Math.max(prev - 1, 0))
  }, [])

  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault()
        goNext()
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault()
        goPrev()
      }
      if (e.key === 'Escape') {
        navigate('/flame-war')
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [goNext, goPrev, navigate])

  if (!data && isFetching) {
    return (
      <div className="fixed inset-0 bg-background flex items-center justify-center z-50">
        <div className="flex flex-col items-center gap-4">
          <Flame className="h-16 w-16 text-orange-500 animate-pulse" />
          <span className="text-xl text-muted-foreground">Loading the heat...</span>
        </div>
      </div>
    )
  }

  if (!data) return null

  const slides = [
    <TitleSlide key="title" weekStart={data.weekStart} weekEnd={data.weekEnd} />,
    <TeamTotalsSlide key="totals" tokens={data.teamTotalTokens} minutes={data.teamTotalMinutes} />,
    <PodiumSlide
      key="tokens-podium"
      title="Top Token Burners"
      icon={Zap}
      podium={data.tokensPodium}
      formatValue={formatNumber}
      color="text-orange-400"
    />,
    <PodiumSlide
      key="time-podium"
      title="Most Time Burned"
      icon={Clock}
      podium={data.timePodium}
      formatValue={formatMinutes}
      color="text-red-400"
    />,
    <RecordsSlide key="records" records={data.records} />,
    <OutroSlide key="outro" />,
  ]

  return (
    <div
      className="fixed inset-0 bg-background z-50 overflow-hidden cursor-pointer select-none"
      onClick={goNext}
    >
      {/* Progress bar */}
      <div className="absolute top-0 left-0 right-0 h-1 bg-muted z-10">
        <motion.div
          className="h-full bg-orange-500"
          animate={{ width: `${((currentSlide + 1) / totalSlides) * 100}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>

      {/* Navigation arrows */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          goPrev()
        }}
        className="absolute left-6 top-1/2 -translate-y-1/2 z-10 p-3 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
        style={{ visibility: currentSlide === 0 ? 'hidden' : 'visible' }}
      >
        <ChevronLeft className="h-8 w-8" />
      </button>
      <button
        onClick={(e) => {
          e.stopPropagation()
          goNext()
        }}
        className="absolute right-6 top-1/2 -translate-y-1/2 z-10 p-3 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
        style={{ visibility: currentSlide === totalSlides - 1 ? 'hidden' : 'visible' }}
      >
        <ChevronRight className="h-8 w-8" />
      </button>

      {/* Slide counter */}
      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 flex gap-2">
        {Array.from({ length: totalSlides }).map((_, i) => (
          <button
            key={i}
            onClick={(e) => {
              e.stopPropagation()
              setCurrentSlide(i)
            }}
            className={`w-2.5 h-2.5 rounded-full transition-colors ${
              i === currentSlide ? 'bg-orange-500' : 'bg-white/20'
            }`}
          />
        ))}
      </div>

      {/* Slides */}
      <AnimatePresence mode="wait">
        <motion.div
          key={currentSlide}
          initial={{ opacity: 0, x: 100 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -100 }}
          transition={{ duration: 0.4 }}
          className="h-full w-full"
        >
          {slides[currentSlide]}
        </motion.div>
      </AnimatePresence>

      {/* Week selector */}
      <div className="absolute top-6 left-6 z-10 flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={goToPrevWeek}
          className="p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex items-center gap-1.5 text-sm text-muted-foreground px-2">
          <Calendar className="h-3.5 w-3.5" />
          {data ? (
            <span>
              {format(new Date(data.weekStart), 'MMM d')} - {format(new Date(data.weekEnd), 'MMM d')}
            </span>
          ) : (
            <span>Loading...</span>
          )}
        </div>
        <button
          onClick={goToNextWeek}
          disabled={isCurrentWeek}
          className="p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        {isFetching && (
          <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-orange-500" />
        )}
      </div>

      {/* ESC hint */}
      <div className="absolute top-6 right-6 z-10 text-xs text-muted-foreground">
        Press ESC to exit
      </div>
    </div>
  )
}

export function WeeklyRecapPage() {
  const { user } = useAuth()

  if (!user?.id || !FLAME_WAR_USER_IDS.includes(user.id)) {
    return <Navigate to="/dashboard" replace />
  }

  return <WeeklyRecapContent />
}
