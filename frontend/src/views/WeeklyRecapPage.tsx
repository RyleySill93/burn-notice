import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Navigate, useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { hasFlameWarAccess } from '@/lib/flame-war-access'
import { Flame, Trophy, Clock, Zap, ChevronLeft, ChevronRight, Calendar, TrendingUp, TrendingDown, Volume2, VolumeX } from 'lucide-react'
import { useSoundEffects, type SoundEffect } from '@/hooks/useSoundEffects'
import { RankingMedal, MilestoneBadge, CrownBadge as CrownBadgeComponent, PurpleHeartBadge, MILESTONE_CONFIGS } from '@/components/badges'
import type { Rank, Metric as BadgeMetric, MilestoneKind, CrownKind } from '@/components/badges'
import { AnimatedFlames } from '@/components/AnimatedFlames'
import { addDays, subDays } from 'date-fns'
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

interface ActionMedalAwarded {
  engineerId: string
  displayName: string
  medalType: string
  citation: string | null
  awardedByDisplayName: string | null
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
  actionsAwarded: ActionMedalAwarded[]
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

type PlaySound = (effect: SoundEffect, options?: { volume?: number; delay?: number; loop?: boolean }) => HTMLAudioElement | undefined

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
        {format(new Date(weekStart), 'MMM d')} - {format(addDays(new Date(weekEnd), 1), 'MMM d, yyyy')}
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
  play,
}: {
  tokens: number
  minutes: number
  prevTokens: number
  prevMinutes: number
  play: PlaySound
}) {
  useEffect(() => {
    play('team-totals', { volume: 0.5 })
  }, [])

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

function CrownsSlide({ crowns, play }: { crowns: CrownHolder[]; play: PlaySound }) {
  useEffect(() => {
    play('celebration', { volume: 0.4 })
    const timer = setTimeout(fireConfettiThenFlames, 600)
    return () => clearTimeout(timer)
  }, [])

  const crownLabels: Record<string, string> = {
    weekly_tokens: 'Tokens',
    weekly_time: 'Time',
  }
  const crownFormatters: Record<string, (v: number) => string> = {
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
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          Crown Holders
        </h2>
      </motion.div>
      <div className="grid grid-cols-2 gap-6 max-w-3xl w-full px-8">
        {crowns.map((crown, i) => {
          const crownKind = crown.crownType.replace('weekly_', '') as CrownKind
          const formatter = crownFormatters[crown.crownType] || formatNumber
          return (
            <motion.div
              key={crown.crownType}
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 + i * 0.15, type: 'spring' }}
              className="flex items-center gap-4 bg-gradient-to-r from-yellow-500/10 to-transparent border border-yellow-500/30 rounded-xl p-5"
            >
              <CrownBadgeComponent kind={crownKind} size={48} />
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
  metricType,
  play,
}: {
  title: string
  icon: typeof Trophy
  podium: PodiumEntry[]
  formatValue: (v: number) => string
  color: string
  medals?: MedalAwarded[]
  metricType: BadgeMetric
  play: PlaySound
}) {
  useEffect(() => {
    play(metricType === 'tokens' ? 'tokens-podium' : 'time-podium', { volume: 0.4 })
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
  const rankToMedalRank: Record<number, Rank> = { 1: 'gold', 2: 'silver', 3: 'bronze' }
  const delays = [0.6, 0.3, 0.9]

  // Map engineer medals by engineerId
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
          const medalRank = rankToMedalRank[entry.rank]
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
                {medalRank && (
                  <RankingMedal
                    rank={medalRank}
                    metric={metricType}
                    count={1}
                    size={visualIdx === 1 ? 72 : visualIdx === 0 ? 60 : 52}
                  />
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

function RecordsSlide({ records, play }: { records: RecapRecord[]; play: PlaySound }) {
  useEffect(() => {
    if (records.length > 0) {
      // Triple airhorn blast for records broken
      play('airhorn', { volume: 0.5 })
      play('airhorn', { volume: 0.4, delay: 300 })
      play('airhorn', { volume: 0.45, delay: 700 })
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

  // Group records by engineer
  const groupByEngineer = (recs: RecapRecord[]) => {
    const map = new Map<string, RecapRecord[]>()
    for (const r of recs) {
      if (!map.has(r.engineerId)) map.set(r.engineerId, [])
      map.get(r.engineerId)!.push(r)
    }
    return Array.from(map.entries())
  }

  const companyByEngineer = groupByEngineer(companyRecords)
  const personalByEngineer = groupByEngineer(personalRecords)

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16 px-8">
      <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} className="flex items-center gap-4">
        <Trophy className="h-12 w-12 text-yellow-400" />
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          Records Broken!
        </h2>
      </motion.div>
      <div className="flex gap-12 w-full max-w-5xl">
        {companyByEngineer.length > 0 && (
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
              {companyByEngineer.map(([engineerId, recs], i) => (
                <EngineerRecordRow key={engineerId} records={recs} delay={0.4 + i * 0.15} />
              ))}
            </div>
          </motion.div>
        )}
        {personalByEngineer.length > 0 && (
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
              {personalByEngineer.map(([engineerId, recs], i) => (
                <EngineerRecordRow key={engineerId} records={recs} delay={0.6 + i * 0.15} />
              ))}
            </div>
          </motion.div>
        )}
      </div>
    </div>
  )
}

function EngineerRecordRow({ records, delay }: { records: RecapRecord[]; delay: number }) {
  const name = records[0].displayName

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ delay, type: 'spring' }}
      className="bg-card border border-border rounded-xl p-4"
    >
      <div className="font-semibold mb-2">{name}</div>
      <div className="flex flex-wrap gap-2">
        {records.map((record, i) => {
          const isTokens = record.recordType === 'tokens'
          const icon = isTokens ? <Zap className="h-3.5 w-3.5 text-orange-400" /> : <Clock className="h-3.5 w-3.5 text-red-400" />
          const valueStr = isTokens ? formatNumber(record.value) : formatMinutes(record.value)
          const prevStr = record.previousValue
            ? isTokens
              ? formatNumber(record.previousValue)
              : formatMinutes(record.previousValue)
            : null
          const periodLabel = record.recordPeriod === 'daily' ? 'Daily' : record.recordPeriod === 'weekly' ? 'Weekly' : 'Monthly'
          const typeLabel = isTokens ? 'Tokens' : 'Time'

          return (
            <div key={i} className="flex items-center gap-2 bg-muted/50 rounded-lg px-3 py-1.5 text-sm">
              {icon}
              <span className="text-xs bg-orange-500/20 text-orange-400 px-1.5 py-0.5 rounded-full">
                {periodLabel} {typeLabel}
              </span>
              <span className="font-bold">{valueStr}</span>
              {prevStr && (
                <span className="text-muted-foreground text-xs">(was {prevStr})</span>
              )}
              <span className="text-muted-foreground text-xs">
                {format(new Date(record.recordDate), 'EEEE, MMMM d yyyy')}
              </span>
            </div>
          )
        })}
      </div>
    </motion.div>
  )
}

function MilestonesSlide({ milestones, play }: { milestones: MilestoneAwarded[]; play: PlaySound }) {
  useEffect(() => {
    play('milestones', { volume: 0.4 })
    const timer = setTimeout(fireConfettiThenFlames, 500)
    return () => clearTimeout(timer)
  }, [])

  // Dedup: only show highest milestone per (engineer, metric_type)
  const TOKEN_MILESTONE_ORDER: string[] = ['token_10b', 'token_1b', 'token_500m', 'token_250m', 'token_100m', 'token_50m', 'token_10m', 'token_1m']
  const TIME_MILESTONE_ORDER: string[] = ['time_25000h', 'time_10000h', 'time_5000h', 'time_2500h', 'time_1000h', 'time_500h', 'time_100h', 'time_10h']

  const deduped = useMemo(() => {
    const seen = new Map<string, MilestoneAwarded>()
    for (const m of milestones) {
      const isToken = m.medalType.startsWith('token_')
      const key = `${m.engineerId}|${isToken ? 'tokens' : 'time'}`
      const existing = seen.get(key)
      if (!existing) {
        seen.set(key, m)
      } else {
        const order = isToken ? TOKEN_MILESTONE_ORDER : TIME_MILESTONE_ORDER
        const existingIdx = order.indexOf(existing.medalType)
        const newIdx = order.indexOf(m.medalType)
        // Lower index = higher tier
        if (newIdx >= 0 && (existingIdx < 0 || newIdx < existingIdx)) {
          seen.set(key, m)
        }
      }
    }
    return Array.from(seen.values())
  }, [milestones])

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-8 py-16">
      <motion.div
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-center gap-4"
      >
        <h2 className="text-5xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
          Milestones Unlocked!
        </h2>
      </motion.div>
      <div className="grid grid-cols-1 gap-4 max-w-2xl w-full px-8">
        {deduped.map((m, i) => {
          const cfg = MILESTONE_CONFIGS[m.medalType as MilestoneKind]
          const label = cfg ? `${cfg.name} — ${cfg.label} ${m.medalType.startsWith('token_') ? 'Tokens' : 'Hours'}` : m.medalType
          return (
            <motion.div
              key={`${m.engineerId}-${m.medalType}`}
              initial={{ opacity: 0, x: -50 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.4 + i * 0.2, type: 'spring' }}
              className="flex items-center gap-5 bg-gradient-to-r from-purple-500/10 to-transparent border border-purple-500/30 rounded-xl p-6"
            >
              <MilestoneBadge kind={m.medalType as MilestoneKind} size={56} />
              <div className="flex-1">
                <div className="font-bold text-xl">{m.displayName}</div>
                <div className="text-purple-300 font-semibold" style={{ fontFamily: 'Bangers, cursive' }}>
                  {label}
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}

function SpecialAwardsSlide({ actions, play }: { actions: ActionMedalAwarded[]; play: PlaySound }) {
  const [phase, setPhase] = useState<'buildup' | 'reveal'>('buildup')

  useEffect(() => {
    // Drumroll during buildup
    const drumrollAudio = play('drumroll', { volume: 0.6, loop: true })

    // Buildup phase with drumroll tension, then reveal
    const revealTimer = setTimeout(() => {
      // Stop drumroll before reveal
      if (drumrollAudio) {
        drumrollAudio.pause()
        drumrollAudio.currentTime = 0
      }
      setPhase('reveal')
      // Yankee doodle fife on reveal
      play('yankee-doodle', { volume: 0.5 })
      // Big dramatic confetti burst on reveal
      setTimeout(() => {
        confetti({
          particleCount: 200,
          spread: 120,
          origin: { y: 0.5 },
          colors: ['#7c3aed', '#c084fc', '#e9d5ff', '#ffd700', '#ffffff'],
          gravity: 0.6,
          ticks: 200,
        })
      }, 400)
    }, 4000)

    return () => clearTimeout(revealTimer)
  }, [])

  return (
    <div className="flex flex-col items-center justify-center min-h-full gap-6 py-16">
      {/* Title - always visible */}
      <motion.div
        initial={{ opacity: 0, y: -30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8 }}
        className="flex flex-col items-center gap-3"
      >
        <motion.div
          animate={{ scale: [1, 1.05, 1] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
        >
          <PurpleHeartBadge size={72} />
        </motion.div>
        <h2 className="text-5xl font-bold text-center" style={{ fontFamily: 'Bangers, cursive' }}>
          Special Commendation
        </h2>
      </motion.div>

      {/* Buildup phase - drumroll tension */}
      {phase === 'buildup' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.8 }}
          className="flex flex-col items-center gap-6"
        >
          {/* Decorative military-style dividers */}
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 1, duration: 1.2, ease: 'easeOut' }}
            className="w-64 h-px bg-gradient-to-r from-transparent via-purple-400/60 to-transparent"
          />

          {/* Pulsing "drumroll" dots */}
          <div className="flex items-center gap-3">
            {[0, 1, 2, 3, 4].map((i) => (
              <motion.div
                key={i}
                className="w-2.5 h-2.5 rounded-full bg-purple-400"
                animate={{
                  scale: [0.5, 1.2, 0.5],
                  opacity: [0.3, 1, 0.3],
                }}
                transition={{
                  duration: 0.6,
                  repeat: Infinity,
                  delay: i * 0.12,
                  ease: 'easeInOut',
                }}
              />
            ))}
          </div>

          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 0.6, 1] }}
            transition={{ delay: 1.5, duration: 2, repeat: Infinity }}
            className="text-lg text-purple-300/80 tracking-widest uppercase"
            style={{ fontFamily: 'Bangers, cursive', letterSpacing: '0.25em' }}
          >
            Attention...
          </motion.p>

          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 1.4, duration: 1.2, ease: 'easeOut' }}
            className="w-64 h-px bg-gradient-to-r from-transparent via-purple-400/60 to-transparent"
          />
        </motion.div>
      )}

      {/* Reveal phase - show the awards */}
      {phase === 'reveal' && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5 }}
          className="flex flex-col items-center gap-6 w-full max-w-2xl px-8"
        >
          {/* Military-style star divider */}
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ duration: 0.6 }}
            className="flex items-center gap-3 w-full"
          >
            <div className="flex-1 h-px bg-gradient-to-r from-transparent to-purple-400/50" />
            <span className="text-purple-400 text-sm">&#9733; &#9733; &#9733;</span>
            <div className="flex-1 h-px bg-gradient-to-l from-transparent to-purple-400/50" />
          </motion.div>

          {actions.map((action, i) => (
            <motion.div
              key={`${action.engineerId}-${action.medalType}-${i}`}
              initial={{ opacity: 0, y: 40, scale: 0.9 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ delay: 0.3 + i * 0.4, type: 'spring', bounce: 0.3 }}
              className="w-full bg-gradient-to-r from-purple-500/15 via-purple-500/10 to-transparent border border-purple-500/30 rounded-xl p-6"
            >
              <div className="flex items-center gap-5">
                <motion.div
                  initial={{ scale: 0, rotate: -90 }}
                  animate={{ scale: 1, rotate: 0 }}
                  transition={{ delay: 0.5 + i * 0.4, type: 'spring', bounce: 0.5 }}
                >
                  <PurpleHeartBadge size={64} />
                </motion.div>
                <div className="flex-1">
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.7 + i * 0.4 }}
                    className="font-bold text-2xl"
                    style={{ fontFamily: 'Bangers, cursive' }}
                  >
                    {action.displayName}
                  </motion.div>
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: 0.9 + i * 0.4 }}
                    className="text-purple-300 font-semibold text-sm uppercase tracking-wider mt-1"
                  >
                    Purple Heart
                  </motion.div>
                  {action.citation && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 1.1 + i * 0.4 }}
                      className="text-muted-foreground text-sm mt-2 italic"
                    >
                      &ldquo;{action.citation}&rdquo;
                    </motion.p>
                  )}
                  {action.awardedByDisplayName && (
                    <motion.p
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ delay: 1.2 + i * 0.4 }}
                      className="text-muted-foreground/60 text-xs mt-1"
                    >
                      Awarded by {action.awardedByDisplayName}
                    </motion.p>
                  )}
                </div>
              </div>
            </motion.div>
          ))}

          {/* Bottom military divider */}
          <motion.div
            initial={{ scaleX: 0 }}
            animate={{ scaleX: 1 }}
            transition={{ delay: 0.3 + actions.length * 0.4, duration: 0.6 }}
            className="flex items-center gap-3 w-full"
          >
            <div className="flex-1 h-px bg-gradient-to-r from-transparent to-purple-400/50" />
            <span className="text-purple-400 text-sm">&#9733; &#9733; &#9733;</span>
            <div className="flex-1 h-px bg-gradient-to-l from-transparent to-purple-400/50" />
          </motion.div>
        </motion.div>
      )}
    </div>
  )
}

function OutroSlide({ play }: { play: PlaySound }) {
  useEffect(() => {
    play('outro', { volume: 0.5 })
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

// Brainrot videos - Subway Surfers, Minecraft parkour, satisfying content, etc.
/**
 * Get the most recent Friday (as a Date) on or before the given date.
 * Uses local time so date-fns format() serializes the correct day.
 */
function getMostRecentFriday(d: Date): Date {
  const day = d.getDay() // 0=Sun, 1=Mon, ..., 5=Fri, 6=Sat
  const daysSinceFriday = (day - 5 + 7) % 7
  const friday = new Date(d)
  friday.setDate(friday.getDate() - daysSinceFriday)
  friday.setHours(12, 0, 0, 0) // Noon to avoid any timezone edge cases
  return friday
}

/**
 * Get the latest week available for burndown.
 * Weeks run Fri-to-Fri. A week's burndown is available after its
 * ending Friday at 9am UTC.
 */
function getLatestAvailableWeekStart(): Date {
  const now = new Date()
  // The Friday that starts the "current" Fri-Fri window
  const currentFriday = getMostRecentFriday(now)

  // The cutoff is the NEXT Friday at 9am UTC (end of this week)
  const nextFriday = new Date(currentFriday)
  nextFriday.setDate(nextFriday.getDate() + 7)
  // Create cutoff in UTC: next Friday at 9am UTC
  const cutoffUtc = Date.UTC(
    nextFriday.getFullYear(), nextFriday.getMonth(), nextFriday.getDate(), 9, 0, 0
  )

  if (now.getTime() >= cutoffUtc) {
    // Current week is done, show it
    return currentFriday
  }
  // Otherwise show the previous week
  const prevFriday = new Date(currentFriday)
  prevFriday.setDate(prevFriday.getDate() - 7)
  prevFriday.setHours(12, 0, 0, 0)
  return prevFriday
}

// Brainrot gameplay videos (muted, background visuals only)
const BRAINROT_VIDEO_IDS = [
  '12LMvdpMhlI',
  'zZ7AimPACzc',
]

function WeeklyRecapContent() {
  const navigate = useNavigate()
  const [currentSlide, setCurrentSlide] = useState(0)
  const [latestWeekStart] = useState(() => getLatestAvailableWeekStart())
  const [asOfDate, setAsOfDate] = useState<Date>(latestWeekStart)
  const [showBrainrotModal, setShowBrainrotModal] = useState(false)
  const brainrotDismissed = useRef(false)
  const [brainrotVisible, setBrainrotVisible] = useState(false)
  const [brainrotVideoId] = useState(() => BRAINROT_VIDEO_IDS[Math.floor(Math.random() * BRAINROT_VIDEO_IDS.length)])
  const { enabled: soundEnabled, toggle: toggleSound, play, stopAll } = useSoundEffects()

  const isLatestWeek = getMostRecentFriday(asOfDate).getTime() === latestWeekStart.getTime()

  const goToPrevWeek = useCallback(() => {
    setAsOfDate((prev) => subDays(prev, 7))
    setCurrentSlide(0)
  }, [])

  const goToNextWeek = useCallback(() => {
    setAsOfDate((prev) => {
      const next = addDays(prev, 7)
      if (getMostRecentFriday(next).getTime() > latestWeekStart.getTime()) return prev
      return next
    })
    setCurrentSlide(0)
  }, [latestWeekStart])

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
    const hasActions = (data.actionsAwarded?.length ?? 0) > 0

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
        play={play}
      />,
    ]

    if (hasCrowns) {
      slideList.push(<CrownsSlide key="crowns" crowns={data.crowns} play={play} />)
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
        metricType="tokens"
        play={play}
      />,
      <PodiumSlide
        key="time-podium"
        title="Most Time Burned"
        icon={Clock}
        podium={data.timePodium}
        formatValue={formatMinutes}
        color="text-red-400"
        medals={timeMedals}
        metricType="time"
        play={play}
      />,
    )

    if (hasRecords) {
      slideList.push(<RecordsSlide key="records" records={data.records} play={play} />)
    }

    if (hasMilestones) {
      slideList.push(<MilestonesSlide key="milestones" milestones={data.milestonesAwarded} play={play} />)
    }

    if (hasActions) {
      slideList.push(<SpecialAwardsSlide key="actions" actions={data.actionsAwarded} play={play} />)
    }

    slideList.push(<OutroSlide key="outro" play={play} />)

    return slideList
  }, [data, play])

  const totalSlides = slides.length

  const goNext = useCallback(() => {
    // Intercept first "next" on title slide to show brainrot modal
    if (currentSlide === 0 && !brainrotDismissed.current) {
      setShowBrainrotModal(true)
      return
    }
    stopAll()
    setCurrentSlide((prev) => Math.min(prev + 1, totalSlides - 1))
  }, [totalSlides, stopAll, currentSlide])

  const handleBrainrotAccept = useCallback(() => {
    setShowBrainrotModal(false)
    brainrotDismissed.current = true
    setBrainrotVisible(true)
    if (!soundEnabled) toggleSound()
    // Play random bruh/fah, then Say So after it ends
    const effect = Math.random() < 0.5 ? 'bruh' : 'fah' as const
    const audio = play(effect, { volume: 0.7 })
    if (audio) {
      audio.addEventListener('ended', () => {
        play('say-so', { volume: 0.5 })
      })
    }
  }, [soundEnabled, toggleSound, play])

  const handleBrainrotDecline = useCallback(() => {
    setShowBrainrotModal(false)
    brainrotDismissed.current = true
    stopAll()
    setCurrentSlide((prev) => Math.min(prev + 1, totalSlides - 1))
  }, [totalSlides, stopAll])

  const goPrev = useCallback(() => {
    stopAll()
    setCurrentSlide((prev) => Math.max(prev - 1, 0))
  }, [stopAll])

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
        navigate('/badges')
      }
      if (e.key === 'z' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setBrainrotVisible((prev) => !prev)
      }
    }
    window.addEventListener('keydown', handleKey, true)
    return () => window.removeEventListener('keydown', handleKey, true)
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

      {/* Animated flames at bottom */}
      <AnimatedFlames intensity="low" />

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
              {format(new Date(data.weekStart), 'MMM d')} - {format(addDays(new Date(data.weekEnd), 1), 'MMM d')}
            </span>
          ) : (
            <span>Loading...</span>
          )}
        </div>
        <button
          onClick={goToNextWeek}
          disabled={isLatestWeek}
          className="p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
        {isFetching && (
          <div className="animate-spin rounded-full h-3.5 w-3.5 border-b-2 border-orange-500" />
        )}
      </div>

      {/* Sound toggle + ESC hint */}
      <div className="absolute top-6 right-6 z-10 flex items-center gap-3" onClick={(e) => e.stopPropagation()}>
        <button
          onClick={toggleSound}
          className="p-1.5 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
          title={soundEnabled ? 'Mute sounds' : 'Unmute sounds'}
        >
          {soundEnabled ? (
            <Volume2 className="h-4 w-4" />
          ) : (
            <VolumeX className="h-4 w-4 text-muted-foreground" />
          )}
        </button>
        <span className="text-xs text-muted-foreground">Press ESC to exit</span>
      </div>

      {/* Gen Z accessibility modal */}
      <AnimatePresence>
        {showBrainrotModal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md"
            onClick={(e) => e.stopPropagation()}
          >
            <motion.div
              initial={{ scale: 0, rotate: -10 }}
              animate={{ scale: 1, rotate: 0 }}
              exit={{ scale: 0, rotate: 10 }}
              transition={{ type: 'spring', damping: 12, stiffness: 200 }}
              className="relative bg-card border-2 border-orange-500/40 rounded-3xl p-10 max-w-lg mx-4 text-center shadow-[0_0_80px_rgba(249,115,22,0.15)]"
            >
              {/* Rotating warning icon */}
              <motion.div
                animate={{ rotate: [0, -10, 10, -10, 0] }}
                transition={{ duration: 0.5, delay: 0.3 }}
                className="text-6xl mb-3"
              >
                🚨
              </motion.div>

              <h2
                className="text-4xl mb-1 bg-gradient-to-r from-red-500 via-orange-500 to-yellow-400 bg-clip-text text-transparent"
                style={{ fontFamily: 'Bangers, cursive', letterSpacing: '2px' }}
              >
                CRITICAL ALERT
              </h2>
              <p className="text-xs text-muted-foreground/60 uppercase tracking-widest mb-5">
                Accessibility Compliance Division
              </p>

              <p className="text-muted-foreground mb-2 text-base leading-relaxed">
                Our systems have detected engineers with birthdays
                <span className="text-orange-400 font-semibold"> after the year 2000</span> in
                attendance.
              </p>
              <p className="text-muted-foreground mb-8 text-base leading-relaxed">
                Federal regulations require activation of
                <span className="font-bold text-foreground"> Gen Z Accessibility Mode</span> to
                ensure comprehension and sustained attention.
              </p>

              <div className="flex gap-4 justify-center items-center">
                <button
                  onClick={handleBrainrotDecline}
                  className="px-5 py-2.5 rounded-xl border border-border/50 text-xs text-muted-foreground hover:bg-muted/50 transition-colors"
                >
                  decline at your own risk
                </button>

                {/* 3D enable button */}
                <motion.button
                  onClick={handleBrainrotAccept}
                  whileHover={{ scale: 1.05, y: -2 }}
                  whileTap={{ scale: 0.95, y: 2 }}
                  className="relative px-8 py-4 rounded-2xl text-white font-bold text-lg cursor-pointer"
                  style={{
                    fontFamily: 'Bangers, cursive',
                    letterSpacing: '2px',
                    background: 'linear-gradient(135deg, #7c3aed, #ec4899, #f97316)',
                    boxShadow: '0 6px 0 #581c87, 0 8px 20px rgba(124,58,237,0.4), 0 0 40px rgba(236,72,153,0.2)',
                    transform: 'translateY(-2px)',
                  }}
                >
                  <span className="flex items-center gap-2 text-xl">
                    🧠 ACTIVATE 🔥
                  </span>
                </motion.button>
              </div>

              {/* Tiny legal disclaimer */}
              <p className="text-[9px] text-muted-foreground/30 mt-6 leading-tight">
                By clicking ACTIVATE you agree to enhanced audio-visual stimulation including but not limited
                to: Subway Surfers gameplay, Minecraft parkour, unhinged sound effects, and involuntary head bobbing.
                Management assumes no liability for lost productivity.
              </p>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Brainrot video overlay (Cmd/Ctrl+Z also toggles) */}
      <AnimatePresence>
        {brainrotVisible && (
          <motion.div
            initial={{ opacity: 0, scale: 0.5, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.5, y: -20 }}
            transition={{ type: 'spring', damping: 20, stiffness: 300 }}
            className="absolute top-16 right-6 z-50 rounded-xl overflow-hidden shadow-2xl border-2 border-orange-500/50"
            onClick={(e) => e.stopPropagation()}
            style={{ width: 280, height: 500 }}
          >
            <iframe
              src={`https://www.youtube.com/embed/${brainrotVideoId}?autoplay=1&mute=1&loop=1&playlist=${brainrotVideoId}&controls=0&modestbranding=1&showinfo=0&rel=0`}
              className="w-full h-full"
              allow="autoplay; encrypted-media"
              allowFullScreen
            />
            <button
              onClick={() => setBrainrotVisible(false)}
              className="absolute top-1 right-1 w-6 h-6 rounded-full bg-black/60 hover:bg-black/80 text-white text-xs flex items-center justify-center transition-colors"
            >
              ✕
            </button>
          </motion.div>
        )}
      </AnimatePresence>
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
