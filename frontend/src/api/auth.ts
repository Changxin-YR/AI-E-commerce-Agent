import { request } from './client'

export interface DemoLogin {
  enabled: boolean
  username?: string
  password?: string
}

export const authApi = {
  demo: () => request<DemoLogin>('/auth/demo'),
}
