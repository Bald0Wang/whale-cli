import DefaultTheme from 'vitepress/theme'
import './custom.css'
import Viz from './Viz.vue'
import OsCommandTabs from './OsCommandTabs.vue'
import WhaleInsight from './WhaleInsight.vue'
import { onMounted } from 'vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app, router }) {
    app.component('Viz', Viz)
    app.component('OsCommandTabs', OsCommandTabs)
    app.component('WhaleInsight', WhaleInsight)

    if (typeof window !== 'undefined') {
      const update = () => {
        const isHome = window.location.pathname === '/' || window.location.pathname === '/index.html'
        document.documentElement.classList.toggle('is-home', isHome)
      }
      router.onAfterRouteChanged = update
      update()
    }
  },
  setup() {
    if (typeof window !== 'undefined') {
      onMounted(() => {
        }
      })
    }
  }
}
