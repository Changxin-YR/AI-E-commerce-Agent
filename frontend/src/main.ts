import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/main.css'
import './styles/soloops.css'
import './styles/android.css'
import { nativeAndroid } from './composables/useAndroidShell'

if (nativeAndroid) document.documentElement.classList.add('native-android')

const app = createApp(App)

app.use(router)

app.mount('#app')
