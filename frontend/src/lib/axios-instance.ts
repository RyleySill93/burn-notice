import Axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Configure axios defaults
const axios = Axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

// Track if we're currently refreshing to avoid multiple refresh calls
let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (error: unknown) => void
}> = []

const processQueue = (error: unknown, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token!)
    }
  })
  failedQueue = []
}

// Add request interceptor for auth token
axios.interceptors.request.use(
  (config) => {
    const sessionStr = localStorage.getItem('SESSION')
    if (sessionStr) {
      try {
        const session = JSON.parse(sessionStr)
        if (session?.accessToken) {
          config.headers.Authorization = `Bearer ${session.accessToken}`
        }
      } catch {
        // Invalid session data
      }
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Add response interceptor for token refresh
axios.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    // Only attempt refresh for 401 errors, not on the refresh endpoint itself, and not if already retried
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/refresh')
    ) {
      if (isRefreshing) {
        // If already refreshing, queue this request
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
          .then((token) => {
            originalRequest.headers.Authorization = `Bearer ${token}`
            return axios(originalRequest)
          })
          .catch((err) => Promise.reject(err))
      }

      originalRequest._retry = true
      isRefreshing = true

      const sessionStr = localStorage.getItem('SESSION')
      if (!sessionStr) {
        isRefreshing = false
        localStorage.removeItem('SESSION')
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        const session = JSON.parse(sessionStr)
        if (!session?.refreshToken) {
          throw new Error('No refresh token')
        }

        // Call refresh endpoint
        const response = await Axios.post(
          `${API_BASE_URL}/auth/refresh`,
          { refresh: session.refreshToken },
          { headers: { 'Content-Type': 'application/json' } }
        )

        const { accessToken, refreshToken } = response.data

        // Update session in localStorage
        const newSession = {
          accessToken,
          refreshToken,
          tokenType: 'Bearer',
        }
        localStorage.setItem('SESSION', JSON.stringify(newSession))

        // Update WebSocket cookie
        const date = new Date()
        date.setTime(date.getTime() + 24 * 60 * 60 * 1000)
        document.cookie = `ws_auth_token=${accessToken}; expires=${date.toUTCString()}; path=/`

        // Process queued requests
        processQueue(null, accessToken)

        // Retry original request
        originalRequest.headers.Authorization = `Bearer ${accessToken}`
        return axios(originalRequest)
      } catch (refreshError) {
        // Refresh failed - clear session and redirect to login
        processQueue(refreshError, null)
        localStorage.removeItem('SESSION')
        document.cookie = 'ws_auth_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;'
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

// Custom instance for generated API client
export const customInstance = <T>(config: AxiosRequestConfig): Promise<T> => {
  const source = Axios.CancelToken.source()
  const promise = axios({
    ...config,
    cancelToken: source.token,
  }).then(({ data }) => data)

  // @ts-ignore
  promise.cancel = () => {
    source.cancel('Query was cancelled')
  }

  return promise
}

export default axios
