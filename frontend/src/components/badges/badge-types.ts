export type Rank = 'gold' | 'silver' | 'bronze'
export type Metric = 'tokens' | 'time'

export type MilestoneKind =
  | 'token_1m'
  | 'token_10m'
  | 'token_50m'
  | 'token_100m'
  | 'token_250m'
  | 'token_500m'
  | 'token_1b'
  | 'token_10b'
  | 'time_10h'
  | 'time_100h'
  | 'time_500h'
  | 'time_1000h'
  | 'time_2500h'
  | 'time_5000h'
  | 'time_10000h'
  | 'time_25000h'

export type CrownKind = 'tokens' | 'time'

export type BaseBadgeProps = {
  className?: string
  size?: number
}
