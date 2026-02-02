import mem from 'mem'
import { type Token } from '../types/auth'
import authService from '../services/authService'

const refreshTokenFn = async (): Promise<Token | undefined> => {
  const session = authService.getSession()

  if (!session) return

  try {
    // TODO: Replace with actual refresh endpoint when available
    // For now, we'll just return the existing token
    // In production, this would call:
    // const result = await apiClient.auth.refreshJwtToken({
    //   refresh: session?.refreshToken,
    // });
    // authService.handleAuthentication(result);
    // return result;

    console.warn('Token refresh not implemented yet, using existing token')
    return session
  } catch (error) {
    authService.logout()
  }
}

const maxAge = 10000

export const memoizedRefreshToken = mem(refreshTokenFn, {
  maxAge,
})
