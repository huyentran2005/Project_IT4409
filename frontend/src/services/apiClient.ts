export const API_BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (typeof detail === 'string') return detail
    // FastAPI 422: detail là mảng lỗi validate
    if (Array.isArray(detail) && detail.length) {
      return detail.map((item: { msg?: string }) => (item.msg ?? '').replace(/^Value error, /, '')).filter(Boolean).join('. ')
    }
  } catch {
    // body không phải JSON
  }
  return `Yêu cầu thất bại (${response.status})`
}

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('taskflow-token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')

  const accessToken = localStorage.getItem('taskflow-token')
  if (accessToken && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  })

  if (!response.ok) {
    throw new ApiError(response.status, await readErrorMessage(response))
  }

  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}
