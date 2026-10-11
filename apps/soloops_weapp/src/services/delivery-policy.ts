export interface ManualDelivery {
  plain_text: string
  csv_text: string
  filename: string
  checked_at: string
}
export function safeFilename(value: string): string {
  const name = value.split(/[\\/]/).pop() || 'soloops.csv'
  return name.replace(/[^a-zA-Z0-9._\-\u4e00-\u9fff]/g, '_').slice(-120)
}
