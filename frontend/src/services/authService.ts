const SESSION = 'SESSION'

export interface AuthSession {
  accessToken: string
  refreshToken: string
  tokenType?: string
}

class AuthService {
  handleAuthentication = (accessToken: string, refreshToken: string): void => {
    const session: AuthSession = {
      accessToken: accessToken,
      refreshToken: refreshToken,
      tokenType: 'Bearer',
    }
    this.setSession(session)
  }

  logout = (): void => {
    this.setSession(null)
    window.location.href = '/login'
  }

  setSession = (session: AuthSession | null): void => {
    this._setCookie(session)
    if (session !== null) {
      localStorage.setItem(SESSION, JSON.stringify(session))
    } else {
      localStorage.removeItem(SESSION)
    }
  }

  getSession = (): AuthSession | null => {
    const session = localStorage.getItem(SESSION)
    if (session !== null) return JSON.parse(session)
    return null
  }

  _setCookie = (session: AuthSession | null) => {
    const date = new Date()
    date.setTime(date.getTime() + 24 * 60 * 60 * 1000)

    if (!session) {
      document.cookie = 'ws_auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;'
    } else {
      document.cookie = `ws_auth_token=${
        session.accessToken
      }; expires=${date.toUTCString()}; path=/`
    }
  }
}

export const authService = new AuthService()
export default authService
