import React, { useState } from 'react'
import { useWebSocketContext } from '../contexts/WebSocketContext'
import { loginWithPassword, setTestToken } from '../utils/testAuth'
import authService from '../services/authService'

export const WebSocketTest: React.FC = () => {
  const { isConnected, websocket } = useWebSocketContext()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')

  const session = authService.getSession()

  const handleLogin = async () => {
    if (email && password) {
      const token = await loginWithPassword(email, password)
      if (token) {
        // Reload to reconnect WebSocket with new token
        window.location.reload()
      }
    }
  }

  const handleSetTestToken = () => {
    setTestToken()
    // Reload to reconnect WebSocket with new token
    window.location.reload()
  }

  const handleLogout = () => {
    authService.logout()
  }

  const sendTestMessage = () => {
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      const testMessage = {
        channel_type: 'test',
        payload: { message: message || 'Hello from frontend!' },
      }
      websocket.send(JSON.stringify(testMessage))
      console.log('Sent message:', testMessage)
    }
  }

  return (
    <div style={{ padding: '20px', border: '1px solid #ccc', margin: '20px' }}>
      <h2>WebSocket Test Panel</h2>

      <div style={{ marginBottom: '10px' }}>
        <strong>Connection Status:</strong>
        <span
          style={{
            marginLeft: '10px',
            color: isConnected ? 'green' : 'red',
            fontWeight: 'bold',
          }}
        >
          {isConnected ? '🟢 Connected' : '🔴 Disconnected'}
        </span>
      </div>

      <div style={{ marginBottom: '10px' }}>
        <strong>Session:</strong> {session ? '✓ Token present' : '✗ No token'}
      </div>

      {!session && (
        <div style={{ marginTop: '20px', padding: '10px', background: '#f0f0f0' }}>
          <h3>Login</h3>
          <div>
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ marginRight: '10px' }}
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ marginRight: '10px' }}
            />
            <button onClick={handleLogin}>Login</button>
          </div>
          <div style={{ marginTop: '10px' }}>
            <button onClick={handleSetTestToken}>Set Test Token (Development Only)</button>
          </div>
        </div>
      )}

      {session && (
        <>
          <div style={{ marginTop: '20px' }}>
            <button onClick={handleLogout}>Logout</button>
          </div>

          {isConnected && (
            <div style={{ marginTop: '20px' }}>
              <h3>Send Test Message</h3>
              <input
                type="text"
                placeholder="Enter message"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                style={{ marginRight: '10px', width: '300px' }}
              />
              <button onClick={sendTestMessage}>Send Message</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
