import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { authService } from '@/services/authService'
import { useAuthenticatePassword, useGenerateEmailChallenge, useRefreshJwtToken, introspectToken } from '@/generated/auth/auth'
import { getMe } from '@/generated/authorization/authorization'
import type { MembershipWithCustomer } from '@/generated/models'

interface User {
  id: string
  email: string
  name?: string
  role?: string
  memberships?: MembershipWithCustomer[]
}

interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  hasMembership: boolean
  isStaff: boolean
  currentCustomerId: string | null
  setCurrentCustomerId: (customerId: string) => void
  login: (email: string, password: string) => Promise<void>
  loginWithMagicLink: (email: string) => Promise<void>
  logout: () => void
  refreshToken: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const CURRENT_CUSTOMER_KEY = 'currentCustomerId'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [hasMembership, setHasMembership] = useState(false)
  const [isStaff, setIsStaff] = useState(false)
  const [currentCustomerId, setCurrentCustomerIdState] = useState<string | null>(
    () => localStorage.getItem(CURRENT_CUSTOMER_KEY)
  )

  const setCurrentCustomerId = (customerId: string) => {
    localStorage.setItem(CURRENT_CUSTOMER_KEY, customerId)
    setCurrentCustomerIdState(customerId)
  }

  // Ensure currentCustomerId is valid for the user's memberships
  const validCustomerId = user?.memberships?.some(m => m.customerId === currentCustomerId)
    ? currentCustomerId
    : user?.memberships?.[0]?.customerId ?? null

  // React Query mutations
  const authenticatePasswordMutation = useAuthenticatePassword()
  const generateEmailChallengeMutation = useGenerateEmailChallenge()
  const refreshTokenMutation = useRefreshJwtToken()

  useEffect(() => {
    // Check for existing session on mount
    const checkAuth = async () => {
      const session = authService.getSession()
      if (session?.accessToken) {
        try {
          // Introspect token to get basic user info
          const tokenInfo = await introspectToken()

          if (tokenInfo?.sub) {
            // Fetch full user info including memberships
            const meData = await getMe()

            setUser({
              id: meData.id,
              email: meData.email,
              name: meData.fullName || undefined,
              memberships: meData.memberships,
            })
            setHasMembership(meData.memberships.length > 0)
            setIsStaff(meData.isStaff)
          } else {
            // Token invalid, clear session
            authService.logout()
          }
        } catch (error) {
          console.error('Auth check failed:', error)
          authService.logout()
        }
      }
      setIsLoading(false)
    }

    checkAuth()
  }, [])

  const login = async (email: string, password: string) => {
    const data = await authenticatePasswordMutation.mutateAsync({
      data: {
        email,
        passwordString: password,
      },
    })

    // Check if MFA is required (MfaToken has 'token' property, Token has 'accessToken')
    if ('token' in data && !('accessToken' in data)) {
      // Return MFA token for MFA flow  
      const mfaData = data as any // Type assertion needed due to union type
      throw new Error('MFA_REQUIRED:' + mfaData.token)
    }

    // Type guard ensures this is Token type
    if (!('accessToken' in data)) {
      throw new Error('Unexpected response format')
    }

    // Cast to Token type after type guard
    const tokenData = data as any // Type assertion needed

    // Store tokens (Token type has accessToken and refreshToken)
    authService.handleAuthentication(tokenData.accessToken, tokenData.refreshToken)

    // Fetch full user info including memberships
    const meData = await getMe()
    setUser({
      id: meData.id,
      email: meData.email,
      name: meData.fullName || undefined,
      memberships: meData.memberships,
    })
    setHasMembership(meData.memberships.length > 0)
    setIsStaff(meData.isStaff)
  }

  const loginWithMagicLink = async (email: string) => {
    await generateEmailChallengeMutation.mutateAsync({
      data: { email },
    })
  }

  const logout = () => {
    authService.logout()
    setUser(null)
  }

  const refreshToken = async () => {
    const session = authService.getSession()
    if (!session?.refreshToken) {
      throw new Error('No refresh token available')
    }

    const data = await refreshTokenMutation.mutateAsync({
      data: { refresh: session.refreshToken },
    })
    
    authService.handleAuthentication(data.accessToken, data.refreshToken)
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        hasMembership,
        isStaff,
        currentCustomerId: validCustomerId,
        setCurrentCustomerId,
        login,
        loginWithMagicLink,
        logout,
        refreshToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
