import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover'
import { Calendar } from '@/components/ui/calendar'
import {
  Flame,
  TrendingUp,
  TrendingDown,
  Minus,
  CalendarIcon,
  Zap,
  Activity,
  BarChart3,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import { format, subDays } from 'date-fns'

interface PeriodStats {
  tokens: number
  comparison_tokens: number
  change_percent: number | null
}

interface UsageStats {
  date: string
  today: PeriodStats
  this_week: PeriodStats
  this_month: PeriodStats
}

interface DailyTotal {
  date: string
  tokens: number
}

interface DailyTotalsResponse {
  start_date: string
  end_date: string
  totals: DailyTotal[]
}

interface LeaderboardEntry {
  engineer_id: string
  display_name: string
  tokens: number
  rank: number
  prev_rank: number | null
  rank_change: number | null
}

interface Leaderboard {
  date: string
  today: LeaderboardEntry[]
  yesterday: LeaderboardEntry[]
  weekly: LeaderboardEntry[]
  monthly: LeaderboardEntry[]
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) {
    return `${(n / 1_000_000).toFixed(1)}M`
  }
  if (n >= 1_000) {
    return `${Math.floor(n / 1_000)}K`
  }
  return n.toString()
}

function ChangeIndicator({ change, delta }: { change: number | null; delta: number }) {
  if (change === null) {
    return <span className="text-sm text-muted-foreground">No prior data</span>
  }
  const deltaStr = delta >= 0 ? `+${formatTokens(delta)}` : `-${formatTokens(Math.abs(delta))}`
  if (change > 0) {
    return (
      <span className="flex items-center gap-1 text-sm text-green-600">
        <TrendingUp className="h-4 w-4" />
        {deltaStr} ({change.toFixed(0)}%)
      </span>
    )
  }
  if (change < 0) {
    return (
      <span className="flex items-center gap-1 text-sm text-red-600">
        <TrendingDown className="h-4 w-4" />
        {deltaStr} ({change.toFixed(0)}%)
      </span>
    )
  }
  return (
    <span className="flex items-center gap-1 text-sm text-muted-foreground">
      <Minus className="h-4 w-4" />
      No change
    </span>
  )
}

function StatCard({
  title,
  tokens,
  comparisonTokens,
  change,
  comparison,
  icon: Icon,
}: {
  title: string
  tokens: number
  comparisonTokens: number
  change: number | null
  comparison: string
  icon: React.ElementType
}) {
  const delta = tokens - comparisonTokens
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{formatTokens(tokens)}</div>
        <div className="flex items-center justify-between mt-1">
          <ChangeIndicator change={change} delta={delta} />
          <span className="text-xs text-muted-foreground">{comparison}</span>
        </div>
      </CardContent>
    </Card>
  )
}

function RankChangeIndicator({ change }: { change: number | null }) {
  if (change === null) {
    return null
  }
  if (change > 0) {
    return (
      <Badge variant="outline" className="gap-1 text-green-600 border-green-200 bg-green-50">
        <TrendingUp className="h-3 w-3" />
        {change}
      </Badge>
    )
  }
  if (change < 0) {
    return (
      <Badge variant="outline" className="gap-1 text-red-600 border-red-200 bg-red-50">
        <TrendingDown className="h-3 w-3" />
        {Math.abs(change)}
      </Badge>
    )
  }
  return (
    <Badge variant="outline" className="gap-1 text-gray-500 border-gray-200">
      <Minus className="h-3 w-3" />
    </Badge>
  )
}

function LeaderboardTable({
  entries,
  emptyMessage,
}: {
  entries: LeaderboardEntry[]
  emptyMessage: string
}) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-8 text-muted-foreground">
        <Flame className="h-8 w-8 mx-auto mb-2 opacity-20" />
        <p className="text-sm">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="space-y-1.5">
      {entries.slice(0, 10).map((entry, index) => (
        <Link
          key={entry.engineer_id}
          to={`/engineers/${entry.engineer_id}`}
          className={cn(
            'flex items-center justify-between p-2.5 rounded-lg border transition-colors hover:border-orange-300',
            index === 0 && 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200',
            index === 1 && 'bg-gradient-to-r from-gray-50 to-slate-50 border-gray-200',
            index === 2 && 'bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200',
            index > 2 && 'bg-white'
          )}
        >
          <div className="flex items-center gap-3">
            <div
              className={cn(
                'w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs',
                index === 0 && 'bg-amber-500 text-white',
                index === 1 && 'bg-gray-400 text-white',
                index === 2 && 'bg-orange-400 text-white',
                index > 2 && 'bg-gray-100 text-gray-600'
              )}
            >
              {entry.rank}
            </div>
            <div>
              <p className="font-medium text-sm hover:text-orange-600">{entry.display_name}</p>
              <p className="text-xs text-muted-foreground">{formatTokens(entry.tokens)} tokens</p>
            </div>
          </div>
          <RankChangeIndicator change={entry.rank_change} />
        </Link>
      ))}
    </div>
  )
}

export function HomePage() {
  const [chartStartDate, setChartStartDate] = useState<Date>(subDays(new Date(), 6))

  const { data: stats, isLoading: statsLoading } = useQuery<UsageStats>({
    queryKey: ['usage-stats'],
    queryFn: async () => {
      const response = await axios.get<UsageStats>('/api/leaderboard/stats')
      return response.data
    },
  })

  const { data: dailyTotals, isLoading: chartLoading } = useQuery<DailyTotalsResponse>({
    queryKey: ['daily-totals', chartStartDate.toISOString()],
    queryFn: async () => {
      const response = await axios.get<DailyTotalsResponse>('/api/leaderboard/daily-totals', {
        params: {
          start_date: format(chartStartDate, 'yyyy-MM-dd'),
          end_date: format(new Date(), 'yyyy-MM-dd'),
        },
      })
      return response.data
    },
  })

  const { data: leaderboard, isLoading: leaderboardLoading } = useQuery<Leaderboard>({
    queryKey: ['leaderboard'],
    queryFn: async () => {
      const response = await axios.get<Leaderboard>('/api/leaderboard')
      return response.data
    },
  })

  const chartData =
    dailyTotals?.totals.map((t) => ({
      date: format(new Date(t.date), 'MMM d'),
      tokens: t.tokens,
    })) || []

  const isLoading = statsLoading || chartLoading || leaderboardLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <StatCard
          title="Today"
          tokens={stats?.today.tokens || 0}
          comparisonTokens={stats?.today.comparison_tokens || 0}
          change={stats?.today.change_percent ?? null}
          comparison="vs yesterday"
          icon={Zap}
        />
        <StatCard
          title="This Week"
          tokens={stats?.this_week.tokens || 0}
          comparisonTokens={stats?.this_week.comparison_tokens || 0}
          change={stats?.this_week.change_percent ?? null}
          comparison="vs last week at this point"
          icon={Activity}
        />
        <StatCard
          title="This Month"
          tokens={stats?.this_month.tokens || 0}
          comparisonTokens={stats?.this_month.comparison_tokens || 0}
          change={stats?.this_month.change_percent ?? null}
          comparison="vs last month at this point"
          icon={BarChart3}
        />
      </div>

      {/* Chart and Leaderboard */}
      <div className="grid gap-6 lg:grid-cols-5 items-start">
        {/* Chart */}
        <Card className="lg:col-span-3">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Daily Token Burns</CardTitle>
            <Popover>
              <PopoverTrigger asChild>
                <Button variant="outline" size="sm" className="gap-2">
                  <CalendarIcon className="h-4 w-4" />
                  {format(chartStartDate, 'MMM d')} - Today
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <Calendar
                  mode="single"
                  selected={chartStartDate}
                  onSelect={(date) => date && setChartStartDate(date)}
                  disabled={(date) => date > new Date() || date < subDays(new Date(), 90)}
                  initialFocus
                />
              </PopoverContent>
            </Popover>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis
                    fontSize={12}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(value) => formatTokens(value)}
                  />
                  <Tooltip
                    formatter={(value: number) => [formatTokens(value), 'Tokens']}
                    labelStyle={{ fontWeight: 'bold' }}
                  />
                  <Bar dataKey="tokens" fill="#f97316" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Leaderboard */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Flame className="h-4 w-4 text-orange-500" />
              Leaderboard
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="today" className="w-full">
              <TabsList className="grid w-full grid-cols-4 mb-4">
                <TabsTrigger value="today" className="text-xs">
                  Today
                </TabsTrigger>
                <TabsTrigger value="yesterday" className="text-xs">
                  Yesterday
                </TabsTrigger>
                <TabsTrigger value="weekly" className="text-xs">
                  Week
                </TabsTrigger>
                <TabsTrigger value="monthly" className="text-xs">
                  Month
                </TabsTrigger>
              </TabsList>
              <TabsContent value="today">
                <LeaderboardTable
                  entries={leaderboard?.today || []}
                  emptyMessage="No usage today yet"
                />
              </TabsContent>
              <TabsContent value="yesterday">
                <LeaderboardTable
                  entries={leaderboard?.yesterday || []}
                  emptyMessage="No usage yesterday"
                />
              </TabsContent>
              <TabsContent value="weekly">
                <LeaderboardTable
                  entries={leaderboard?.weekly || []}
                  emptyMessage="No usage this week"
                />
              </TabsContent>
              <TabsContent value="monthly">
                <LeaderboardTable
                  entries={leaderboard?.monthly || []}
                  emptyMessage="No usage this month"
                />
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
