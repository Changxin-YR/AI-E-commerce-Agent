import { request } from './client'
import type { Onboarding, SellerProfile, Session, Shop, ShopInput } from '@/types/identity'

export const identityApi = {
  login: (username: string, password: string) =>
    request<Session>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  session: () => request<Session>('/auth/session'),
  logout: () => request<void>('/auth/logout', { method: 'POST' }),
  profile: () => request<SellerProfile | null>('/profile'),
  saveProfile: (data: SellerProfile) =>
    request<SellerProfile>('/profile', { method: 'PUT', body: JSON.stringify(data) }),
  shops: () => request<Shop[]>('/shops'),
  createShop: (data: ShopInput) =>
    request<Shop>('/shops', { method: 'POST', body: JSON.stringify(data) }),
  onboarding: () => request<Onboarding>('/onboarding'),
}
