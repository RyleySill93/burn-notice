import { useState } from 'react'
import { Settings, Copy, Check, Github } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/contexts/AuthContext'
import { SuperButton } from '@/components/SuperButton'
import { useApiError } from '@/hooks/useApiError'
import { useGetMyApiKey } from '@/generated/invitations/invitations'
import {
  useGetGithubStatus,
  useGetGithubConnectUrl,
  useDisconnectGithub,
} from '@/generated/github/github'

export function SetupPage() {
  const { customer, user } = useAuth()
  const [copied, setCopied] = useState(false)
  const [isHovered, setIsHovered] = useState(false)
  const apiError = useApiError()
  const apiUrl = import.meta.env.VITE_API_BASE_URL

  if (!apiUrl) {
    throw new Error('VITE_API_BASE_URL environment variable is required')
  }

  // For now, we'll use the user's ID as the engineer ID
  // In production, this should be mapped to the actual engineer record
  const engineerId = user?.id ?? ''

  // API key query
  const { data: myApiKey, isLoading } = useGetMyApiKey(
    { customer_id: customer?.id ?? '' },
    { query: { enabled: !!customer?.id } }
  )

  // GitHub connection status
  const {
    data: githubStatus,
    isLoading: isLoadingGitHub,
    refetch: refetchGitHubStatus,
  } = useGetGithubStatus(engineerId, { query: { enabled: !!engineerId } })

  // GitHub connect URL query (enabled on demand)
  const { refetch: fetchConnectUrl } = useGetGithubConnectUrl(
    { engineer_id: engineerId },
    { query: { enabled: false } }
  )

  // GitHub disconnect mutation
  const disconnectMutation = useDisconnectGithub()

  const handleConnectGitHub = async () => {
    if (!engineerId) return
    apiError.clearError()
    try {
      const result = await fetchConnectUrl()
      if (result.data?.authorizationUrl) {
        window.location.href = result.data.authorizationUrl
      }
    } catch (err) {
      apiError.setError(err)
    }
  }

  const handleDisconnectGitHub = async () => {
    if (!engineerId) return
    apiError.clearError()
    try {
      await disconnectMutation.mutateAsync({ engineerId })
      refetchGitHubStatus()
    } catch (err) {
      apiError.setError(err)
    }
  }

  const apiKey = myApiKey?.api_key

  // Display any errors from GitHub operations
  const { ErrorAlert } = apiError

  const setupScript = apiKey
    ? `# burn-notice - Claude Code usage tracking
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json
export OTEL_EXPORTER_OTLP_ENDPOINT="${apiUrl}"
export OTEL_EXPORTER_OTLP_HEADERS="X-API-Key=${apiKey}"`
    : ''

  const handleCopyScript = async () => {
    await navigator.clipboard.writeText(setupScript)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
      </div>
    )
  }

  return (
    <div className="min-h-[60vh] flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl">
        <CardHeader className="text-center">
          <Settings className="h-12 w-12 text-primary mx-auto mb-4" />
          <CardTitle>Setup Instructions</CardTitle>
          <CardDescription>
            Configure Claude Code to track your usage on the leaderboard.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {ErrorAlert}
          {apiKey && (
            <div>
              <h3 className="font-semibold mb-2">Shell Configuration</h3>
              <p className="text-sm text-muted-foreground mb-3">
                Add to <code className="bg-muted px-1.5 py-0.5 rounded text-xs">~/.zshrc</code> (or <code className="bg-muted px-1.5 py-0.5 rounded text-xs">~/.bashrc</code>), then run: <code className="bg-muted px-1.5 py-0.5 rounded text-xs">source ~/.zshrc</code>
              </p>
              <div
                className="relative bg-zinc-900 text-zinc-100 rounded-lg p-4 font-mono text-sm overflow-x-auto"
                onMouseEnter={() => setIsHovered(true)}
                onMouseLeave={() => setIsHovered(false)}
              >
                <button
                  onClick={handleCopyScript}
                  className={`absolute top-2 right-2 p-1.5 rounded bg-zinc-700 hover:bg-zinc-600 transition-opacity duration-200 ${
                    isHovered || copied ? 'opacity-100' : 'opacity-0'
                  }`}
                  title="Copy to clipboard"
                >
                  {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4 text-zinc-300" />}
                </button>
                <pre>{setupScript}</pre>
              </div>
            </div>
          )}
          {!apiKey && (
            <p className="text-sm text-yellow-600 text-center">
              Unable to load your API key. Please try refreshing the page.
            </p>
          )}

          {/* GitHub Integration Section */}
          <div className="mt-6 pt-6 border-t">
            <h3 className="font-semibold mb-2">GitHub Integration</h3>
            <p className="text-sm text-muted-foreground mb-3">
              Connect your GitHub account to track commits, PRs, and code reviews on the leaderboard.
            </p>
            {isLoadingGitHub ? (
              <div className="flex items-center justify-center py-4">
                <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary" />
              </div>
            ) : githubStatus?.connected ? (
              <div className="flex items-center justify-between p-3 bg-green-50 dark:bg-green-900/20 rounded-lg border border-green-200 dark:border-green-800">
                <div className="flex items-center gap-2">
                  <Github className="h-5 w-5 text-green-600 dark:text-green-400" />
                  <span className="text-sm">
                    Connected as <strong>@{githubStatus.githubUsername}</strong>
                  </span>
                </div>
                <SuperButton
                  variant="outline"
                  size="sm"
                  onClick={handleDisconnectGitHub}
                >
                  Disconnect
                </SuperButton>
              </div>
            ) : (
              <SuperButton onClick={handleConnectGitHub} leftIcon={Github}>
                Connect GitHub
              </SuperButton>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
