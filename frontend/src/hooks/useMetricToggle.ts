import { useSearchParams } from 'react-router'

export type MetricType =
  | 'total' | 'input' | 'output' | 'cost'  // Token metrics
  | 'commits' | 'additions' | 'deletions' | 'lines' | 'prs'  // GitHub metrics
  | 'time'  // Activity metrics

export type MetricCategory = 'tokens' | 'github' | 'activity'

export function getMetricCategory(metric: MetricType): MetricCategory {
  if (metric === 'commits' || metric === 'additions' || metric === 'deletions' || metric === 'lines' || metric === 'prs') {
    return 'github'
  }
  if (metric === 'time') {
    return 'activity'
  }
  return 'tokens'
}

export function isGitHubMetric(metric: MetricType): boolean {
  return getMetricCategory(metric) === 'github'
}

export function useMetricToggle() {
  const [searchParams, setSearchParams] = useSearchParams()
  const metric = (searchParams.get('metric') as MetricType) || 'total'

  const setMetric = (newMetric: MetricType) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev)
      if (newMetric === 'total') {
        next.delete('metric')
      } else {
        next.set('metric', newMetric)
      }
      return next
    })
  }

  return { metric, setMetric }
}
