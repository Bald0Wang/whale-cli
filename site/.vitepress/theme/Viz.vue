<template>
  <div class="viz-wrapper" data-viz-shell>
    <div class="viz-header">
      <div class="viz-heading">
        <span class="viz-title">{{ title }}</span>
      </div>
      <div class="viz-actions">
        <button class="viz-expand" type="button" @click="expand" :aria-label="`全屏查看：${title}`">点击此处可全屏操作</button>
      </div>
    </div>
    <iframe
      :src="src"
      :title="title"
      class="viz-iframe"
      loading="lazy"
      @load="enhanceFrame"
    ></iframe>
  </div>
  <Teleport to="body">
    <div v-if="expanded" class="viz-overlay" role="dialog" aria-modal="true" :aria-label="title" @click.self="close">
      <div class="viz-overlay-bar">
        <span><i aria-hidden="true"></i>{{ title }}</span>
        <button ref="closeButton" class="viz-overlay-close" type="button" @click="close">关闭</button>
      </div>
      <iframe :src="src" :title="`全屏：${title}`" class="viz-overlay-iframe" @load="enhanceFrame"></iframe>
    </div>
  </Teleport>
</template>

<script setup>
import { nextTick, ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  src: { type: String, required: true },
  title: { type: String, default: '' },
  height: { type: String, default: '500px' },
})

const expanded = ref(false)
const closeButton = ref(null)

function expand() { expanded.value = true }
function close() { expanded.value = false }

function enhanceFrame(event) {
  try {
    const doc = event.target.contentDocument
    if (!doc || doc.getElementById('whale-viz-foundation-css')) return

    const stylesheet = doc.createElement('link')
    stylesheet.id = 'whale-viz-foundation-css'
    stylesheet.rel = 'stylesheet'
    stylesheet.href = '/viz/viz-foundation.css'
    doc.head.appendChild(stylesheet)

    const script = doc.createElement('script')
    script.id = 'whale-viz-foundation-js'
    script.src = '/viz/viz-foundation.js'
    doc.body.appendChild(script)
  } catch {
    // Viz files are same-origin in production. Ignore external embeds gracefully.
  }
}

function onKey(e) {
  if (e.key === 'Escape') close()
}

watch(expanded, async (isOpen) => {
  document.documentElement.style.overflow = isOpen ? 'hidden' : ''
  if (isOpen) {
    await nextTick()
    closeButton.value?.focus()
  }
})

onMounted(() => document.addEventListener('keydown', onKey))
onUnmounted(() => {
  document.removeEventListener('keydown', onKey)
  document.documentElement.style.overflow = ''
})
</script>

<style scoped>
.viz-wrapper {
  margin: 1.4rem 0 1.8rem;
  border: 1px solid color-mix(in srgb, var(--vp-c-text-1) 16%, transparent);
  border-radius: 14px;
  overflow: hidden;
  background: var(--vp-c-bg);
  box-shadow: 0 18px 52px -42px color-mix(in srgb, var(--vp-c-text-1) 54%, transparent);
}
.viz-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 10px 12px 10px 14px;
  background: var(--vp-c-bg-soft);
  border-bottom: 1px solid color-mix(in srgb, var(--vp-c-text-1) 10%, transparent);
  font-size: 12px;
  color: var(--vp-c-text-2);
}
.viz-heading { display: grid; gap: 2px; min-width: 0; }
.viz-overlay-bar i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #df6f4f;
  box-shadow: 0 0 0 4px color-mix(in srgb, #df6f4f 16%, transparent);
}
.viz-title {
  overflow: hidden;
  color: var(--vp-c-text-1);
  font-weight: 650;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.viz-actions { display: flex; align-items: center; flex: none; }
.viz-expand {
  min-height: 30px;
  border: none;
  background: linear-gradient(135deg, #d97757, #c45f3c);
  cursor: pointer;
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  padding: 6px 16px;
  border-radius: 999px;
  box-shadow: 0 2px 8px rgba(217,119,87,0.25);
  transition: box-shadow .2s ease, transform .2s ease, opacity .2s ease;
  opacity: 0.85;
}
.viz-expand:hover { opacity: 1; box-shadow: 0 4px 14px rgba(217,119,87,0.35); transform: translateY(-1px); }
.viz-expand:focus-visible,
.viz-overlay-close:focus-visible { outline: 3px solid #efb43d; outline-offset: 2px; }
.viz-iframe {
  width: 100%;
  height: v-bind(height);
  border: none;
  display: block;
}
.viz-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(19, 17, 15, 0.92);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 18px;
  backdrop-filter: blur(14px);
}
.viz-overlay-bar {
  width: min(94vw, 1500px);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 0 2px 10px;
  color: rgba(255, 255, 255, .82);
  font-size: 12px;
  font-weight: 600;
}
.viz-overlay-bar span { display: flex; align-items: center; gap: 9px; }
.viz-overlay-close {
  min-height: 32px;
  border: 1px solid rgba(255,255,255,0.22);
  background: rgba(255,255,255,0.1);
  color: #fff;
  font: inherit;
  font-weight: 650;
  border-radius: 8px;
  cursor: pointer;
  padding: 5px 12px;
}
.viz-overlay-close:hover { background: rgba(255,255,255,0.3); }
.viz-overlay-iframe {
  width: min(94vw, 1500px);
  height: min(88vh, 980px);
  border: 1px solid rgba(255,255,255,0.16);
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 30px 90px rgba(0,0,0,.5);
}

@media (max-width: 640px) {
  .viz-hint { display: none; }
  .viz-header { align-items: flex-start; }
  .viz-title { white-space: normal; }
  .viz-overlay { padding: 10px; }
  .viz-overlay-bar,
  .viz-overlay-iframe { width: 96vw; }
}

@media (prefers-reduced-motion: reduce) {
  .viz-expand { transition: none; }
}
</style>
