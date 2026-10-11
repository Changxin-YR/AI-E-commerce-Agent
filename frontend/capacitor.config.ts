import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'com.soloops.android',
  appName: 'SoloOps',
  webDir: 'dist',
  server: { androidScheme: 'https', cleartext: false },
  plugins: { CapacitorHttp: { enabled: true } },
}

export default config
