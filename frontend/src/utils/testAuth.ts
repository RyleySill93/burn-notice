// Temporary test authentication helper
// This should be replaced with proper authentication flow in production

import authService from '../services/authService'
import type { Token } from '../types/auth'
import { authenticatePassword } from '@/generated/auth/auth'

export const setTestToken = async () => {
  // This won't work with a fake token - you need a real JWT from the backend
  console.error('⚠️ WARNING: Setting a fake token will cause WebSocket connection to fail!')
  console.log('To get a real token:')
  console.log('1. Create a user in the database')
  console.log('2. Use the login form with real credentials')
  console.log('3. Or manually generate a JWT token from the backend')

  // Don't set a fake token as it will cause infinite reconnection attempts
  alert('Please use real login credentials instead. Check the console for instructions.')
  return

  // If you have a real JWT token, you can uncomment and use this:
  // const testToken: Token = {
  //   accessToken: "YOUR_REAL_JWT_TOKEN_HERE",
  //   refreshToken: "YOUR_REAL_REFRESH_TOKEN_HERE",
  //   tokenType: "Bearer"
  // };
  // authService.setSession(testToken);
}

// Helper to login with email/password (when backend is ready)
export const loginWithPassword = async (email: string, password: string): Promise<Token | null> => {
  try {
    const token = await authenticatePassword({
      email,
      passwordString: password,
    })

    // Check if it's an MFA token (has mfaToken field)
    if ('mfaToken' in token) {
      console.log('MFA required. Please implement MFA flow.')
      return null
    }

    // Store the token (only if it's a full Token, not MfaToken)
    if ('accessToken' in token && 'refreshToken' in token) {
      authService.setSession(token)
      return token
    }

    return null
  } catch (error) {
    console.error('Login error:', error)
    return null
  }
}
