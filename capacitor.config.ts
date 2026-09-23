import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.jakeharvey.ash',
  appName: 'Ash',
  webDir: 'dist',
  server: {
    androidScheme: 'https'
  },
  android: {
    allowMixedContent: false,
    backgroundColor: '#07090d'
  }
};

export default config;
