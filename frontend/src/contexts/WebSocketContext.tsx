import React, { createContext, useContext, useRef, useCallback, useEffect, useState } from 'react'

import { memoizedRefreshToken } from '../utils/refreshToken'
import { authService } from '../services/authService'
import { config } from '@/config/app'

const INITIAL_RECONNECT_DELAY = 1000
const MAX_RECONNECT_DELAY = 30000
const MAX_RECONNECT_ATTEMPTS = 5

interface WebSocketContextType {
  websocket: WebSocket | null
  isConnected: boolean
}

const WebSocketContext = createContext<WebSocketContextType>({
  websocket: null,
  isConnected: false,
})

export const useWebSocketContext = () => {
  const context = useContext(WebSocketContext)
  if (!context) {
    throw new Error('useWebSocketContext must be used within WebSocketProvider')
  }
  return context
}

interface WebSocketProviderProps {
  children: React.ReactNode
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const reconnectAttemptsRef = useRef(0)
  const [isConnected, setIsConnected] = useState(false)

  const connect = useCallback(async (shouldRefreshToken = false) => {
    try {
      // Don't create a new connection if one already exists and is open
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return
      }

      // 401s should try to refresh the token first
      if (shouldRefreshToken) {
        const newToken = await memoizedRefreshToken()
        if (!newToken) {
          console.error('Failed to refresh token')
          return
        }
      }

      const socketUrl = `${config.wsBaseUrl}/ws`
      const session = authService.getSession()

      if (!session?.accessToken) {
        console.log('No access token available, skipping WebSocket connection')
        // Don't logout if there's no token - user might not be logged in yet
        return
      }

      console.log('Attempting WebSocket connection to:', socketUrl)
      console.log('Using token:', session.accessToken.substring(0, 20) + '...')

      const socket = new WebSocket(socketUrl, ['message', session.accessToken])

      socket.onopen = () => {
        console.log('Global WebSocket connected')
        setIsConnected(true)
        reconnectAttemptsRef.current = 0
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current)
        }
      }

      socket.onmessage = (event) => {
        const data = JSON.parse(event.data)

        // Handle 401 response from the WebSocket server
        if (data.code === 401) {
          socket.close()
          if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
            const delay = Math.min(
              INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
              MAX_RECONNECT_DELAY
            )
            reconnectAttemptsRef.current += 1
            reconnectTimeoutRef.current = setTimeout(() => {
              // Reconnect with token refresh
              connect(true)
            }, delay)
          } else {
            console.error('Max reconnection attempts reached')
            authService.logout()
          }
        }

        // All message handling is done by individual hooks listening to this WebSocket
      }

      socket.onclose = (event) => {
        console.log('Global WebSocket disconnected')
        console.log('Close code:', event.code)
        console.log('Close reason:', event.reason)
        console.log('Was clean:', event.wasClean)
        setIsConnected(false)
        wsRef.current = null

        // Handle specific close codes that should not reconnect
        if (event.code === 1008) {
          // Policy violation (no token)
          console.log('Stopping reconnection: Policy violation (no token)')
          return
        }
        if (event.code === 1000) {
          // Normal closure - don't reconnect
          console.log('Stopping reconnection: Normal closure')
          return
        }

        // Check if this is an authentication failure (1001 with specific reasons)
        if (
          event.code === 1001 &&
          (event.reason === 'Invalid access token' || event.reason === 'Expired access token')
        ) {
          console.log('Stopping reconnection: Authentication failed -', event.reason)
          // For expired tokens, we could try to refresh, but for invalid tokens, stop
          if (event.reason === 'Invalid access token') {
            // Clear the invalid token
            authService.setSession(null)
            return
          }
          // For expired tokens, try to refresh once
          if (reconnectAttemptsRef.current === 0) {
            reconnectAttemptsRef.current = 1
            setTimeout(() => {
              connect(true) // Try with refresh
            }, 1000)
          }
          return
        }

        // Codes that should trigger reconnection regardless of wasClean
        const shouldReconnect =
          event.code === 1012 || // Service restart
          event.code === 1013 || // Try again later
          event.code === 1006 || // Abnormal closure
          event.code === 1011 || // Server error
          !event.wasClean

        if (shouldReconnect && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
            MAX_RECONNECT_DELAY
          )
          reconnectAttemptsRef.current += 1
          reconnectTimeoutRef.current = setTimeout(() => {
            connect(false)
          }, delay)
        }
      }

      socket.onerror = (error) => {
        console.error('Global WebSocket error:', error)
        socket.close()
      }

      wsRef.current = socket
    } catch (error) {
      console.error('Failed to connect Global WebSocket:', error)
      setIsConnected(false)
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(
          INITIAL_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
          MAX_RECONNECT_DELAY
        )
        reconnectAttemptsRef.current += 1
        reconnectTimeoutRef.current = setTimeout(() => {
          connect(false)
        }, delay)
      }
    }
  }, [])

  useEffect(() => {
    connect(false)

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
    }
  }, [connect])

  return (
    <WebSocketContext.Provider value={{ websocket: wsRef.current, isConnected }}>
      {children}
    </WebSocketContext.Provider>
  )
}
