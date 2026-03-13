import { useState } from 'react'
import { Navigate, Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { hasFlameWarAccess } from '@/lib/flame-war-access'
import { Award, Presentation, Medal, Heart, Crown } from 'lucide-react'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { RankingMedal, MilestoneBadge, CrownBadge, PurpleHeartBadge, MILESTONE_CONFIGS } from '@/components/badges'
import type { Rank, Metric, MilestoneKind, CrownKind } from '@/components/badges'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'

interface BadgeLeaderboardEntry {
  engineerId: string
  displayName: string
  gold: number
  silver: number
  bronze: number
  tokenMilestone: string | null  // e.g. 'token_100m'
  timeMilestone: string | null   // e.g. 'time_1000h'
  tokenCrown: boolean
  timeCrown: boolean
  purpleHearts: number
  total: number
}

interface BadgeLeaderboardData {
  entries: BadgeLeaderboardEntry[]
}

type BadgeTab = 'leaderboard' | 'directory'

const RANKING_MEDALS: { rank: Rank; metric: Metric; label: string; description: string }[] = [
  { rank: 'gold', metric: 'tokens', label: 'Gold — Tokens', description: 'Weekly #1 in tokens burned' },
  { rank: 'silver', metric: 'tokens', label: 'Silver — Tokens', description: 'Weekly #2 in tokens burned' },
  { rank: 'bronze', metric: 'tokens', label: 'Bronze — Tokens', description: 'Weekly #3 in tokens burned' },
  { rank: 'gold', metric: 'time', label: 'Gold — Time', description: 'Weekly #1 in coding time' },
  { rank: 'silver', metric: 'time', label: 'Silver — Time', description: 'Weekly #2 in coding time' },
  { rank: 'bronze', metric: 'time', label: 'Bronze — Time', description: 'Weekly #3 in coding time' },
]

const CROWNS: { kind: CrownKind; label: string; description: string }[] = [
  { kind: 'tokens', label: 'Token Crown', description: 'Holds the all-time weekly record for tokens burned' },
  { kind: 'time', label: 'Time Crown', description: 'Holds the all-time weekly record for coding time' },
]

const TOKEN_MILESTONES: MilestoneKind[] = [
  'token_1m', 'token_10m', 'token_50m', 'token_100m',
  'token_250m', 'token_500m', 'token_1b', 'token_10b',
]

const TIME_MILESTONES: MilestoneKind[] = [
  'time_10h', 'time_100h', 'time_500h', 'time_1000h',
  'time_2500h', 'time_5000h', 'time_10000h', 'time_25000h',
]

// --- Badge Directory components ---

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-4">
      <h2 className="text-2xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>{title}</h2>
      <p className="text-sm text-muted-foreground">{subtitle}</p>
    </div>
  )
}

function BadgeCard({ badge, label, description }: { badge: React.ReactNode; label: string; description: string }) {
  return (
    <div className="flex items-center gap-4 rounded-xl border bg-card p-4">
      <div className="shrink-0">{badge}</div>
      <div className="min-w-0">
        <div className="font-semibold">{label}</div>
        <div className="text-sm text-muted-foreground">{description}</div>
      </div>
    </div>
  )
}

function BadgeDirectory() {
  return (
    <div className="space-y-10">
      <section>
        <SectionHeader title="Crowns" subtitle="Awarded to the current holder of a company record. Only one person holds each crown at a time." />
        <div className="grid gap-3 sm:grid-cols-2">
          {CROWNS.map((c) => (
            <BadgeCard
              key={c.kind}
              badge={<CrownBadge kind={c.kind} size={56} />}
              label={c.label}
              description={c.description}
            />
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="Weekly Medals" subtitle="Awarded to the top 3 each week. Collect multiples — the count shows on the badge." />
        <div className="grid gap-3 sm:grid-cols-2">
          {RANKING_MEDALS.map((m) => (
            <BadgeCard
              key={`${m.rank}-${m.metric}`}
              badge={<RankingMedal rank={m.rank} metric={m.metric} count={1} size={56} />}
              label={m.label}
              description={m.description}
            />
          ))}
        </div>
      </section>

      <section>
        <SectionHeader title="Token Milestones" subtitle="Earned once when you hit cumulative token thresholds. Only your highest is displayed." />
        <div className="grid gap-3 sm:grid-cols-2">
          {TOKEN_MILESTONES.map((kind) => {
            const cfg = MILESTONE_CONFIGS[kind]
            return (
              <BadgeCard
                key={kind}
                badge={<MilestoneBadge kind={kind} size={56} />}
                label={`${cfg.name} — ${cfg.label}`}
                description={`Burn ${cfg.label} total tokens`}
              />
            )
          })}
        </div>
      </section>

      <section>
        <SectionHeader title="Time Milestones" subtitle="Earned once when you hit cumulative coding hour thresholds. Only your highest is displayed." />
        <div className="grid gap-3 sm:grid-cols-2">
          {TIME_MILESTONES.map((kind) => {
            const cfg = MILESTONE_CONFIGS[kind]
            return (
              <BadgeCard
                key={kind}
                badge={<MilestoneBadge kind={kind} size={56} />}
                label={`${cfg.name} — ${cfg.label}`}
                description={`Accumulate ${cfg.label} of coding time`}
              />
            )
          })}
        </div>
      </section>

      <section>
        <SectionHeader title="Special" subtitle="Manually awarded by teammates for acts of valor." />
        <div className="grid gap-3 sm:grid-cols-2">
          <BadgeCard
            badge={<PurpleHeartBadge size={56} />}
            label="Purple Heart"
            description="Awarded by a teammate with a citation for going above and beyond"
          />
        </div>
      </section>
    </div>
  )
}

// --- Badge Leaderboard components ---

// Milestone ordering for sort comparisons (higher index = higher milestone)
const TOKEN_MILESTONE_RANK: Record<string, number> = {
  token_1m: 1, token_10m: 2, token_50m: 3, token_100m: 4,
  token_250m: 5, token_500m: 6, token_1b: 7, token_10b: 8,
}
const TIME_MILESTONE_RANK: Record<string, number> = {
  time_10h: 1, time_100h: 2, time_500h: 3, time_1000h: 4,
  time_2500h: 5, time_5000h: 6, time_10000h: 7, time_25000h: 8,
}

type SortKey = 'total' | 'gold' | 'silver' | 'bronze' | 'tokenMilestone' | 'timeMilestone' | 'tokenCrown' | 'timeCrown' | 'purpleHearts'

function getSortValue(entry: BadgeLeaderboardEntry, key: SortKey): number {
  switch (key) {
    case 'total': return entry.total
    case 'gold': return entry.gold
    case 'silver': return entry.silver
    case 'bronze': return entry.bronze
    case 'tokenMilestone': return entry.tokenMilestone ? (TOKEN_MILESTONE_RANK[entry.tokenMilestone] ?? 0) : 0
    case 'timeMilestone': return entry.timeMilestone ? (TIME_MILESTONE_RANK[entry.timeMilestone] ?? 0) : 0
    case 'tokenCrown': return entry.tokenCrown ? 1 : 0
    case 'timeCrown': return entry.timeCrown ? 1 : 0
    case 'purpleHearts': return entry.purpleHearts
  }
}

function CountCell({ count, highlight }: { count: number; highlight?: boolean }) {
  return (
    <span className={cn(
      'tabular-nums text-sm',
      count === 0 && 'text-muted-foreground/40',
      highlight && count > 0 && 'font-bold',
    )}>
      {count}
    </span>
  )
}

function BadgeLeaderboard() {
  const [sortBy, setSortBy] = useState<SortKey>('total')

  const { data, isLoading } = useQuery<BadgeLeaderboardData>({
    queryKey: ['badge-leaderboard'],
    queryFn: async () => {
      const response = await axios.get<BadgeLeaderboardData>('/api/leaderboard/badge-leaderboard')
      return response.data
    },
  })

  const sorted = data?.entries
    ? [...data.entries].sort((a, b) => getSortValue(b, sortBy) - getSortValue(a, sortBy))
    : []

  const columns: { key: SortKey; label: string; icon: React.ReactNode }[] = [
    { key: 'total', label: 'Total', icon: <Award className="h-3.5 w-3.5" /> },
    { key: 'gold', label: 'Gold', icon: <RankingMedal rank="gold" metric="tokens" count={0} size={20} /> },
    { key: 'silver', label: 'Silver', icon: <RankingMedal rank="silver" metric="tokens" count={0} size={20} /> },
    { key: 'bronze', label: 'Bronze', icon: <RankingMedal rank="bronze" metric="tokens" count={0} size={20} /> },
    { key: 'tokenMilestone', label: 'Tokens', icon: <Medal className="h-3.5 w-3.5" /> },
    { key: 'timeMilestone', label: 'Time', icon: <Medal className="h-3.5 w-3.5" /> },
    { key: 'tokenCrown', label: 'Tokens', icon: <Crown className="h-3.5 w-3.5" /> },
    { key: 'timeCrown', label: 'Time', icon: <Crown className="h-3.5 w-3.5" /> },
    { key: 'purpleHearts', label: 'Hearts', icon: <Heart className="h-3.5 w-3.5" /> },
  ]

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-base">Badge Leaderboard</CardTitle>
      </CardHeader>
      <CardContent>
        <TooltipProvider delayDuration={200}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b text-xs text-muted-foreground">
                <th className="text-left py-2 pr-4 font-medium">#</th>
                <th className="text-left py-2 pr-4 font-medium">Engineer</th>
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      'py-2 px-2 font-medium text-center cursor-pointer hover:text-foreground transition-colors',
                      sortBy === col.key && 'text-foreground',
                    )}
                    onClick={() => setSortBy(col.key)}
                  >
                    <div className="flex items-center justify-center gap-1">
                      {col.icon}
                      <span className="hidden sm:inline">{col.label}</span>
                      {sortBy === col.key && <span className="text-orange-500">&#9660;</span>}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((entry, i) => (
                <tr key={entry.engineerId} className="border-b last:border-0 hover:bg-muted/50 transition-colors">
                  <td className="py-3 pr-4 text-sm text-muted-foreground tabular-nums">{i + 1}</td>
                  <td className="py-3 pr-4">
                    <Link
                      to={`/engineers/${entry.engineerId}`}
                      className="font-medium text-sm hover:underline"
                    >
                      {entry.displayName}
                    </Link>
                  </td>
                  <td className="py-3 px-2 text-center">
                    <CountCell count={entry.total} highlight={sortBy === 'total'} />
                  </td>
                  <td className="py-3 px-2 text-center">
                    <CountCell count={entry.gold} highlight={sortBy === 'gold'} />
                  </td>
                  <td className="py-3 px-2 text-center">
                    <CountCell count={entry.silver} highlight={sortBy === 'silver'} />
                  </td>
                  <td className="py-3 px-2 text-center">
                    <CountCell count={entry.bronze} highlight={sortBy === 'bronze'} />
                  </td>
                  <td className="py-3 px-2 text-center">
                    {entry.tokenMilestone ? (() => {
                      const cfg = MILESTONE_CONFIGS[entry.tokenMilestone as MilestoneKind]
                      return (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="flex justify-center cursor-default">
                              <MilestoneBadge kind={entry.tokenMilestone as MilestoneKind} size={28} />
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-72 text-center">
                            <p className="text-sm font-medium">{cfg.name} — {cfg.label} tokens burned</p>
                          </TooltipContent>
                        </Tooltip>
                      )
                    })() : (
                      <span className="text-muted-foreground/30">—</span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-center">
                    {entry.timeMilestone ? (() => {
                      const cfg = MILESTONE_CONFIGS[entry.timeMilestone as MilestoneKind]
                      return (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <div className="flex justify-center cursor-default">
                              <MilestoneBadge kind={entry.timeMilestone as MilestoneKind} size={28} />
                            </div>
                          </TooltipTrigger>
                          <TooltipContent side="bottom" className="max-w-72 text-center">
                            <p className="text-sm font-medium">{cfg.name} — {cfg.label} coding hours</p>
                          </TooltipContent>
                        </Tooltip>
                      )
                    })() : (
                      <span className="text-muted-foreground/30">—</span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-center">
                    {entry.tokenCrown ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex justify-center cursor-default">
                            <CrownBadge kind="tokens" size={28} />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-72 text-center">
                          <p className="text-sm font-medium">Company Record · Most Tokens Burned</p>
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <span className="text-muted-foreground/30">—</span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-center">
                    {entry.timeCrown ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex justify-center cursor-default">
                            <CrownBadge kind="time" size={28} />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-72 text-center">
                          <p className="text-sm font-medium">Company Record · Most Coding Time</p>
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <span className="text-muted-foreground/30">—</span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-center">
                    {entry.purpleHearts > 0 ? (
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <div className="flex justify-center cursor-default">
                            <PurpleHeartBadge size={28} />
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="bottom" className="max-w-72 text-center">
                          <p className="text-sm font-medium">Purple Heart × {entry.purpleHearts}</p>
                        </TooltipContent>
                      </Tooltip>
                    ) : (
                      <span className="text-muted-foreground/30">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </TooltipProvider>
      </CardContent>
    </Card>
  )
}

// --- Main Page ---

export function BadgeDirectoryPage() {
  const { user } = useAuth()
  const [tab, setTab] = useState<BadgeTab>('leaderboard')

  if (!hasFlameWarAccess(user?.id)) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Award className="h-7 w-7 text-orange-500" />
          <div>
            <h1 className="text-2xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>
              Badges
            </h1>
            <p className="text-muted-foreground text-sm">Leaderboard and badge directory</p>
          </div>
        </div>
        <Link
          to="/weekly-recap"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium transition-colors"
        >
          <Presentation className="h-4 w-4" />
          Weekly Recap
        </Link>
      </div>

      {/* Tab Selector */}
      <Tabs value={tab} onValueChange={(v) => setTab(v as BadgeTab)}>
        <TabsList>
          <TabsTrigger value="leaderboard" className="text-xs">Leaderboard</TabsTrigger>
          <TabsTrigger value="directory" className="text-xs">Badge Directory</TabsTrigger>
        </TabsList>
      </Tabs>

      {/* Content */}
      {tab === 'leaderboard' && <BadgeLeaderboard />}
      {tab === 'directory' && <BadgeDirectory />}
    </div>
  )
}
