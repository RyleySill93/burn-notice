import { Navigate, Link } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import { hasFlameWarAccess } from '@/lib/flame-war-access'
import { ArrowLeft } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { RankingMedal, MilestoneBadge, CrownBadge, PurpleHeartBadge, MILESTONE_CONFIGS } from '@/components/badges'
import type { Rank, Metric, MilestoneKind, CrownKind } from '@/components/badges'

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

export function BadgeDirectoryPage() {
  const { user } = useAuth()

  if (!hasFlameWarAccess(user?.id)) {
    return <Navigate to="/dashboard" replace />
  }

  return (
    <div className="max-w-3xl mx-auto space-y-10 pb-16">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/flame-war">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-3xl font-bold" style={{ fontFamily: 'Bangers, cursive' }}>Badge Directory</h1>
          <p className="text-muted-foreground text-sm">All the badges you can earn</p>
        </div>
      </div>

      {/* Crowns */}
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

      {/* Ranking Medals */}
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

      {/* Token Milestones */}
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

      {/* Time Milestones */}
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

      {/* Purple Heart */}
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
