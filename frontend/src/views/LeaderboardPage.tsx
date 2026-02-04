import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Badge } from '@/components/ui/badge'
import { Flame, TrendingUp, TrendingDown, Minus, Sparkles } from 'lucide-react'
import { cn } from '@/lib/utils'
import axios from '@/lib/axios-instance'


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

function RankChangeIndicator({ change }: { change: number | null }) {
  if (change === null) {
    return (
      <Badge variant="outline" className="gap-1 text-purple-600 border-purple-200 bg-purple-50">
        <Sparkles className="h-3 w-3" />
        NEW
      </Badge>
    )
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

function LeaderboardTable({ entries, emptyMessage }: { entries: LeaderboardEntry[]; emptyMessage: string }) {
  if (entries.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <Flame className="h-12 w-12 mx-auto mb-4 opacity-20" />
        <p>{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {entries.map((entry, index) => (
        <Link
          key={entry.engineer_id}
          to={`/engineers/${entry.engineer_id}`}
          className={cn(
            'flex items-center justify-between p-4 rounded-lg border transition-colors hover:border-orange-300',
            index === 0 && 'bg-gradient-to-r from-amber-50 to-orange-50 border-amber-200',
            index === 1 && 'bg-gradient-to-r from-gray-50 to-slate-50 border-gray-200',
            index === 2 && 'bg-gradient-to-r from-orange-50 to-amber-50 border-orange-200',
            index > 2 && 'bg-white'
          )}
        >
          <div className="flex items-center gap-4">
            <div
              className={cn(
                'w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm',
                index === 0 && 'bg-amber-500 text-white',
                index === 1 && 'bg-gray-400 text-white',
                index === 2 && 'bg-orange-400 text-white',
                index > 2 && 'bg-gray-100 text-gray-600'
              )}
            >
              {entry.rank}
            </div>
            <div>
              <p className="font-medium hover:text-orange-600">{entry.display_name}</p>
              <p className="text-sm text-muted-foreground">{formatTokens(entry.tokens)} tokens</p>
            </div>
          </div>
          <RankChangeIndicator change={entry.rank_change} />
        </Link>
      ))}
    </div>
  )
}

export function LeaderboardPage() {

  const { data: leaderboard, isLoading } = useQuery<Leaderboard>({
    queryKey: ['leaderboard'],
    queryFn: async () => {
      const response = await axios.get<Leaderboard>('/api/leaderboard')
      return response.data
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  return (
    <div className="container max-w-4xl py-8">
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Flame className="h-8 w-8 text-orange-500" />
          <h1 className="text-3xl" style={{ fontFamily: 'Bangers, cursive' }}>burn notice</h1>
        </div>
        <p className="text-muted-foreground">
          Who's burning the most tokens on your team?
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>Leaderboard</span>
            {leaderboard && (
              <span className="text-sm font-normal text-muted-foreground">
                {new Date(leaderboard.date).toLocaleDateString('en-US', {
                  weekday: 'long',
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric',
                })}
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="today" className="w-full">
            <TabsList className="grid w-full grid-cols-4 mb-6">
              <TabsTrigger value="today">Today</TabsTrigger>
              <TabsTrigger value="yesterday">Yesterday</TabsTrigger>
              <TabsTrigger value="weekly">Weekly</TabsTrigger>
              <TabsTrigger value="monthly">Monthly</TabsTrigger>
            </TabsList>
            <TabsContent value="today">
              <LeaderboardTable
                entries={leaderboard?.today || []}
                emptyMessage="No usage recorded today yet. Start burning tokens!"
              />
            </TabsContent>
            <TabsContent value="yesterday">
              <LeaderboardTable
                entries={leaderboard?.yesterday || []}
                emptyMessage="No usage recorded yesterday."
              />
            </TabsContent>
            <TabsContent value="weekly">
              <LeaderboardTable
                entries={leaderboard?.weekly || []}
                emptyMessage="No usage recorded this week yet."
              />
            </TabsContent>
            <TabsContent value="monthly">
              <LeaderboardTable
                entries={leaderboard?.monthly || []}
                emptyMessage="No usage recorded this month yet."
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}
