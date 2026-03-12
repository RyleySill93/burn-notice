import { useState, useEffect, useCallback, useMemo } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { hasFlameWarAccess } from '@/lib/flame-war-access'
import { Flame, Trophy, Clock, Zap, ChevronLeft, ChevronRight, Crown, Medal, Award, Calendar, TrendingUp, TrendingDown, Star } from 'lucide-react'
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

interface CrownHolder {
  engineerId: string
  displayName: string
  crownType: string
  value: number
  recordDate: string
}

interface MedalAwarded {
  engineerId: string
  displayName: string
  medalType: string
  metricType: string
  periodType: string
  value: number
}

interface MilestoneAwarded {
  engineerId: string
  displayName: string
  medalType: string
  value: number
}

interface WeeklyRecapData {
  weekStart: string
  weekEnd: string
  tokensPodium: PodiumEntry[]
  timePodium: PodiumEntry[]
  records: RecapRecord[]
  teamTotalTokens: number
  teamTotalMinutes: number
  crowns: CrownHolder[]
  medalsAwarded: MedalAwarded[]
  milestonesAwarded: MilestoneAwarded[]
  prevWeekTokens: number
  prevWeekMinutes: number
}

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

function fireFlames() {
  confetti({
    particleCount: 50,
    angle: 90,
    spread: 60,
    origin: { x: 0.5, y: 1.0 },
    colors: ['#ff4500', '#ff6a00', '#ff8c00', '#ffa500'],
    gravity: 0.8,
    ticks: 100,
  })
  confetti({
    particleCount: 30,
    angle: 80,
    spread: 40,
    origin: { x: 0.3, y: 1.0 },
    colors: ['#ff4500', '#ff6a00', '#ff8c00', '#ffa500'],
    gravity: 0.8,
    ticks: 80,
  })
  confetti({
    particleCount: 30,
    angle: 100,
    spread: 40,
    origin: { x: 0.7, y: 1.0 },
    colors: ['#ff4500', '#ff6a00', '#ff8c00', '#ffa500'],
    gravity: 0.8,
    ticks: 80,
  })
}

function fireConfettiThenFlames() {
  fireBigConfetti()
  setTimeout(fireFlames, 800)
}

function getWoWPercent(current: number, previous: number): number | null {
  if (previous === 0) return null
  return ((current - previous) / previous) * 100
}

// --- Slide Components ---

function TitleSlide({ weekStart, weekEnd }: { weekStart: string; weekEnd: string }) {
  useEffect(() => {
    const timer = setTimeout(() => {
      fireConfetti()
      setTimeout(fireFlames, 2000)
    }, 500)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
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
        The Burndown
      </motion.h1>
      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1, duration: 0.5 }}
        className="text-2xl text-muted-foreground"
      >
        {format(new Date(weekStart), 'MMM d')} - {format(new Date(weekEnd), 'MMM d, yyyy')}
      </motion.p>
      {/* Flame gradient at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-orange-500/20 via-orange-500/5 to-transparent pointer-events-none" />
    </div>
  )
}

function WoWDelta({ current, previous, format: fmt }: { current: number; previous: number; format: (n: number) => string }) {
  const pct = getWoWPercent(current, previous)
  if (pct === null) return null

  const isUp = pct >= 0
  const Icon = isUp ? TrendingUp : TrendingDown
  const color = isUp ? 'text-green-400' : 'text-red-400'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 2.5 }}
      className={`flex items-center gap-1.5 text-sm ${color}`}
    >
      <Icon className="h-4 w-4" />
      <span>{isUp ? '+' : ''}{pct.toFixed(0)}% vs last week</span>
      <span className="text-muted-foreground">({fmt(previous)})</span>
    </motion.div>
  )
}

function TeamTotalsSlide({
  tokens,
  minutes,
  prevTokens,
  prevMinutes,
}: {
  tokens: number
  minutes: number
  prevTokens: number
  prevMinutes: number
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-12 py-16">
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
          <WoWDelta current={tokens} previous={prevTokens} format={formatNumber} />
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
          <WoWDelta current={minutes} previous={prevMinutes} format={formatMinutes} />
        </motion.div>
      </div>
    </div>
  )
}

function CrownsSlide({ crowns }: { crowns: CrownHolder[] }) {
  useEffect(() => {
    const timer = setTimeout(fireConfettiThenFlames, 600)
    return () => clearTimeout(timer)
  }, [])

  const crownLabels: Record<string, string> = {
    daily_tokens: 'Daily Tokens',
    daily_time: 'Daily Time',
    weekly_tokens: 'Weekly Tokens',
    weekly_time: 'Weekly Time',
  }
  const crownIcons: Record<string, typeof Zap> = {
    daily_tokens: Zap,
    daily_time: Clock,
    weekly_tokens: Zap,
    weekly_time: Clock,
  }
  const crownFormatters: Record<string, (v: number) => string> = {
    daily_tokens: formatNumber,
    daily_time: formatMinutes,
    weekly_tokens: formatNumber,
    weekly_time: formatMinutes,
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
      <motion.div
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4"
      >
        <Crown className="h-12 w-12 text-yellow-400" />
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          Crown Holders
        </h2>
      </motion.div>
      <div className="grid grid-cols-2 gap-6 max-w-3xl w-full px-8">
        {crowns.map((crown, i) => {
          const CrownIcon = crownIcons[crown.crownType] || Zap
          const formatter = crownFormatters[crown.crownType] || formatNumber
          return (
            <motion.div
              key={crown.crownType}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 + i * 0.15, type: 'spring' }}
              className="flex items-center gap-4 bg-gradient-to-r from-yellow-500/10 to-transparent border border-yellow-500/30 rounded-xl p-5"
            >
              <div className="relative">
                <CrownIcon className="h-8 w-8 text-yellow-400/50" />
                <Crown className="h-5 w-5 text-yellow-400 absolute -top-2 -right-2" />
              </div>
              <div className="flex-1">
                <div className="text-xs text-yellow-400/70 uppercase tracking-wider font-semibold">
                  {crownLabels[crown.crownType] || crown.crownType}
                </div>
                <div className="font-bold text-lg">{crown.displayName}</div>
                <div className="text-sm text-muted-foreground">{formatter(crown.value)}</div>
              </div>
            </motion.div>
          )
        })}
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
  medals,
}: {
  title: string
  icon: typeof Trophy
  podium: PodiumEntry[]
  formatValue: (v: number) => string
  color: string
  medals?: MedalAwarded[]
}) {
  useEffect(() => {
    const timer = setTimeout(fireConfettiThenFlames, 1200)
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
  const medalColors: Record<string, string> = {
    gold: 'text-yellow-400',
    silver: 'text-gray-400',
    bronze: 'text-amber-700',
  }
  const delays = [0.6, 0.3, 0.9]

  // Map engineer medals by rank
  const medalByEngineer = new Map<string, string>()
  if (medals) {
    for (const m of medals) {
      medalByEngineer.set(m.engineerId, m.medalType)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
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
          const engineerMedal = medalByEngineer.get(entry.engineerId)
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
                className="flex items-center gap-1"
              >
                {rankIcons[visualIdx]}
                {engineerMedal && (
                  <Medal className={`h-5 w-5 ${medalColors[engineerMedal] || 'text-yellow-400'}`} />
                )}
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
      {/* Flame gradient at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-24 bg-gradient-to-t from-orange-500/10 to-transparent pointer-events-none" />
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
      <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
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
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16 px-8">
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

function MilestonesSlide({ milestones }: { milestones: MilestoneAwarded[] }) {
  useEffect(() => {
    const timer = setTimeout(fireConfettiThenFlames, 500)
    return () => clearTimeout(timer)
  }, [])

  const milestoneLabels: Record<string, string> = {
    token_1m: 'Spark — 1M Tokens',
    token_10m: 'Ember — 10M Tokens',
    token_50m: 'Blaze — 50M Tokens',
    token_100m: 'Inferno — 100M Tokens',
    token_250m: 'Firestorm — 250M Tokens',
    token_500m: 'Supernova — 500M Tokens',
    token_1b: 'Solar Flare — 1 BILLION Tokens',
    token_10b: 'Big Bang — 10 BILLION Tokens',
    time_10h: 'Clocked In — 10 Hours',
    time_100h: 'Grinder — 100 Hours',
    time_500h: 'Marathoner — 500 Hours',
    time_1000h: 'Ironman — 1,000 Hours',
    time_2500h: 'Centurion — 2,500 Hours',
    time_5000h: 'Titan — 5,000 Hours',
    time_10000h: 'Eternal — 10,000 Hours',
    time_25000h: 'Transcendent — 25,000 Hours',
  }
  const milestoneIcons: Record<string, typeof Zap> = {
    token_1m: Zap,
    token_10m: Zap,
    token_50m: Zap,
    token_100m: Zap,
    token_250m: Zap,
    token_500m: Zap,
    token_1b: Zap,
    token_10b: Zap,
    time_10h: Clock,
    time_100h: Clock,
    time_500h: Clock,
    time_1000h: Clock,
    time_2500h: Clock,
    time_5000h: Clock,
    time_10000h: Clock,
    time_25000h: Clock,
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
      <motion.div
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4"
      >
        <Star className="h-12 w-12 text-purple-400" />
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          Milestones Unlocked!
        </h2>
      </motion.div>
      <div className="grid grid-cols-1 gap-4 max-w-2xl w-full px-8">
        {milestones.map((m, i) => {
          const MIcon = milestoneIcons[m.medalType] || Star
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + i * 0.2, type: 'spring' }}
              className="flex items-center gap-5 bg-gradient-to-r from-purple-500/10 to-transparent border border-purple-500/30 rounded-xl p-6"
            >
              <div className="relative">
                <MIcon className="h-10 w-10 text-purple-400" />
                <Star className="h-4 w-4 text-yellow-400 absolute -top-1 -right-1 fill-yellow-400" />
              </div>
              <div className="flex-1">
                <div className="font-bold text-xl">{m.displayName}</div>
                <div className="text-purple-300 font-semibold" style={{ fontFamily: 'Bangers, cursive' }}>
                  {milestoneLabels[m.medalType] || m.medalType}
                </div>
              </div>
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ delay: 0.6 + i * 0.2, type: 'spring', bounce: 0.5 }}
              >
                <Medal className="h-8 w-8 text-purple-400" />
              </motion.div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function OutroSlide() {
  useEffect(() => {
    const timer = setTimeout(() => {
      fireConfetti()
      setTimeout(fireFlames, 2000)
    }, 300)
    return () => clearTimeout(timer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
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
      {/* Flame gradient at bottom */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-orange-500/20 via-orange-500/5 to-transparent pointer-events-none" />
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

  // Build dynamic slides based on data
  const slides = useMemo(() => {
    if (!data) return []

    const hasCrowns = data.crowns.length > 0
    const hasRecords = data.records.length > 0
    const hasMilestones = data.milestonesAwarded.length > 0

    // Map medals by metric type for podium slides
    const tokenMedals = data.medalsAwarded.filter((m) => m.metricType === 'tokens')
    const timeMedals = data.medalsAwarded.filter((m) => m.metricType === 'time')

    const slideList: React.ReactElement[] = [
      <TitleSlide key="title" weekStart={data.weekStart} weekEnd={data.weekEnd} />,
      <TeamTotalsSlide
        key="totals"
        tokens={data.teamTotalTokens}
        minutes={data.teamTotalMinutes}
        prevTokens={data.prevWeekTokens}
        prevMinutes={data.prevWeekMinutes}
      />,
    ]

    if (hasCrowns) {
      slideList.push(<CrownsSlide key="crowns" crowns={data.crowns} />)
    }

    slideList.push(
      <PodiumSlide
        key="tokens-podium"
        title="Top Token Burners"
        icon={Zap}
        podium={data.tokensPodium}
        formatValue={formatNumber}
        color="text-orange-400"
        medals={tokenMedals}
      />,
      <PodiumSlide
        key="time-podium"
        title="Most Time Burned"
        icon={Clock}
        podium={data.timePodium}
        formatValue={formatMinutes}
        color="text-red-400"
        medals={timeMedals}
      />,
    )

    if (hasRecords) {
      slideList.push(<RecordsSlide key="records" records={data.records} />)
    }

    if (hasMilestones) {
      slideList.push(<MilestonesSlide key="milestones" milestones={data.milestonesAwarded} />)
    }

    slideList.push(<OutroSlide key="outro" />)

    return slideList
  }, [data])

  const totalSlides = slides.length

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
          className="h-full w-full overflow-y-auto"
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

  if (!hasFlameWarAccess(user?.id)) {
    return <Navigate to="/dashboard" replace />
  }

  return <WeeklyRecapContent />
}
