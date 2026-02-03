import Axios, { type AxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Configure axios defaults
const axios = Axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
})

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
    if (error.response?.status === 401) {
      // Could add token refresh logic here
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
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
