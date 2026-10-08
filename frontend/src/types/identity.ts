export interface Session {
  user_id: number
  username: string
  csrf_token: string
}

export interface SellerProfile {
  display_name: string
  target_market: string
  business_model: string
  category: string
  currency: string
  timezone: string
  language: string
  version: number
}

export interface ShopInput {
  code: string
  name: string
  platform: string
  market: string
  currency: string
  timezone: string
}

export interface Shop extends ShopInput {
  id: number
  connection_status: 'file_only'
}

export interface Onboarding {
  profile_complete: boolean
  shop_count: number
  data_mode: 'file_import'
  next_step: 'profile' | 'shop' | 'import'
}

export const currencies = ['USD', 'CNY', 'EUR', 'GBP', 'JPY', 'CAD', 'AUD', 'HKD', 'SGD']
export const timezones = [
  'Asia/Shanghai',
  'America/New_York',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Asia/Tokyo',
  'UTC',
]
