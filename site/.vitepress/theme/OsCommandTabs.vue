<script setup>
import { nextTick, onMounted, onUnmounted, ref, useId, useSlots } from 'vue'

const STORAGE_KEY = 'whale-docs-os'
const CHANGE_EVENT = 'whale-docs-os-change'

const operatingSystems = [
  { id: 'windows', label: 'Windows', terminal: 'PowerShell' },
  { id: 'macos', label: 'macOS', terminal: 'Terminal' },
  { id: 'linux', label: 'Linux', terminal: 'Shell' },
]

const slots = useSlots()
const instanceId = useId()
const activeOs = ref('windows')
const tabButtons = ref([])

const tabId = os => `${instanceId}-os-tab-${os}`
const panelId = os => `${instanceId}-os-panel-${os}`

function availableSystems() {
  return operatingSystems.filter(({ id }) => Boolean(slots[id]))
}

function detectOperatingSystem() {
  const userAgent = window.navigator.userAgent.toLowerCase()
  const platform = (window.navigator.userAgentData?.platform || window.navigator.platform || '').toLowerCase()

  if (platform.includes('win') || userAgent.includes('windows')) return 'windows'
  if (platform.includes('mac') || userAgent.includes('mac os')) return 'macos'
  return 'linux'
}

function isAvailable(os) {
  return availableSystems().some(({ id }) => id === os)
}

function selectOs(os, { announce = true, focus = false } = {}) {
  if (!isAvailable(os)) return

  activeOs.value = os

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, os)
    if (announce) window.dispatchEvent(new CustomEvent(CHANGE_EVENT, { detail: os }))
  }

  if (focus) {
    nextTick(() => {
      const index = availableSystems().findIndex(({ id }) => id === os)
      tabButtons.value[index]?.focus()
    })
  }
}

function handleGlobalChange(event) {
  selectOs(event.detail, { announce: false })
}

function handleKeydown(event, currentIndex) {
  const systems = availableSystems()
  let nextIndex = currentIndex

  if (event.key === 'ArrowRight') nextIndex = (currentIndex + 1) % systems.length
  else if (event.key === 'ArrowLeft') nextIndex = (currentIndex - 1 + systems.length) % systems.length
  else if (event.key === 'Home') nextIndex = 0
  else if (event.key === 'End') nextIndex = systems.length - 1
  else return

  event.preventDefault()
  selectOs(systems[nextIndex].id, { focus: true })
}

onMounted(() => {
  const saved = window.localStorage.getItem(STORAGE_KEY)
  selectOs(isAvailable(saved) ? saved : detectOperatingSystem(), { announce: false })
  window.addEventListener(CHANGE_EVENT, handleGlobalChange)
})

onUnmounted(() => window.removeEventListener(CHANGE_EVENT, handleGlobalChange))
</script>

<template>
  <section class="os-command-tabs">
    <header class="os-command-header">
      <div class="os-command-title">
        <span class="terminal-mark" aria-hidden="true">&gt;_</span>
        <span>选择你的终端</span>
      </div>
      <span class="preference-note">选择会应用到整本教程</span>
    </header>

    <div class="os-tab-list" role="tablist" aria-label="选择操作系统">
      <button
        v-for="(system, index) in availableSystems()"
        :id="tabId(system.id)"
        :key="system.id"
        :ref="el => { if (el) tabButtons[index] = el }"
        class="os-tab"
        :class="{ active: activeOs === system.id }"
        type="button"
        role="tab"
        :aria-selected="activeOs === system.id"
        :aria-controls="panelId(system.id)"
        :tabindex="activeOs === system.id ? 0 : -1"
        @click="selectOs(system.id)"
        @keydown="handleKeydown($event, index)"
      >
        <span class="os-indicator" :class="`os-indicator-${system.id}`" aria-hidden="true"></span>
        <span>{{ system.label }}</span>
        <small>{{ system.terminal }}</small>
      </button>
    </div>

    <div
      v-for="system in availableSystems()"
      v-show="activeOs === system.id"
      :id="panelId(system.id)"
      :key="system.id"
      class="os-panel"
      role="tabpanel"
      :aria-labelledby="tabId(system.id)"
    >
      <slot :name="system.id"></slot>
    </div>
  </section>
</template>

<style scoped>
.os-command-tabs {
  --os-accent: #f07b3f;
  --os-ink: var(--vp-c-text-1);
  margin: 18px 0 24px;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
  border-top: 3px solid var(--os-accent);
  border-radius: 10px;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--os-accent) 5%, transparent) 1px, transparent 1px) 0 0 / 22px 22px,
    var(--vp-c-bg-soft);
  box-shadow: 0 12px 30px color-mix(in srgb, var(--vp-c-text-1) 8%, transparent);
}

.os-command-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-height: 42px;
  padding: 8px 14px;
  border-bottom: 1px solid var(--vp-c-divider);
  background: color-mix(in srgb, var(--vp-c-bg) 92%, transparent);
}

.os-command-title {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  color: var(--os-ink);
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0.02em;
}

.terminal-mark {
  display: inline-grid;
  width: 27px;
  height: 22px;
  place-items: center;
  border-radius: 4px;
  background: var(--vp-c-text-1);
  color: var(--vp-c-bg);
  font-family: "Cascadia Code", "SFMono-Regular", Consolas, monospace;
  font-size: 11px;
  letter-spacing: -0.08em;
}

.preference-note {
  color: var(--vp-c-text-3);
  font-size: 11px;
}

.os-tab-list {
  display: flex;
  gap: 2px;
  padding: 0 10px;
  overflow-x: auto;
  border-bottom: 1px solid var(--vp-c-divider);
  background: var(--vp-c-bg);
  scrollbar-width: thin;
}

.os-tab {
  position: relative;
  display: inline-flex;
  align-items: baseline;
  gap: 7px;
  min-width: 126px;
  padding: 12px 13px 10px;
  border: 0;
  background: transparent;
  color: var(--vp-c-text-2);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
  transition: color 160ms ease, background-color 160ms ease;
}

.os-tab::after {
  position: absolute;
  right: 12px;
  bottom: -1px;
  left: 12px;
  height: 2px;
  background: var(--os-accent);
  content: "";
  opacity: 0;
  transform: scaleX(0.35);
  transition: opacity 160ms ease, transform 160ms ease;
}

.os-tab:hover {
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
}

.os-tab:focus-visible {
  border-radius: 5px;
  outline: 2px solid var(--os-accent);
  outline-offset: -3px;
}

.os-tab.active {
  color: var(--vp-c-text-1);
  font-weight: 650;
}

.os-tab.active::after {
  opacity: 1;
  transform: scaleX(1);
}

.os-tab small {
  color: var(--vp-c-text-3);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.os-indicator {
  width: 7px;
  height: 7px;
  flex: 0 0 auto;
  border-radius: 50%;
  background: #8a8f98;
  box-shadow: 0 0 0 3px color-mix(in srgb, #8a8f98 14%, transparent);
}

.os-indicator-windows { background: #2589d8; box-shadow: 0 0 0 3px color-mix(in srgb, #2589d8 14%, transparent); }
.os-indicator-macos { background: #8a8f98; }
.os-indicator-linux { background: #e5a323; box-shadow: 0 0 0 3px color-mix(in srgb, #e5a323 16%, transparent); }

.os-panel {
  padding: 12px;
  background: color-mix(in srgb, var(--vp-c-bg) 94%, transparent);
}

.os-panel :deep(div[class*='language-']) {
  margin: 0;
  border-radius: 7px;
  box-shadow: none;
}

.os-panel :deep(div[class*='language-'] + div[class*='language-']) {
  margin-top: 10px;
}

.os-panel :deep(p:first-child) { margin-top: 0; }
.os-panel :deep(p:last-child) { margin-bottom: 0; }

@media (max-width: 640px) {
  .preference-note { display: none; }
  .os-tab { min-width: 112px; }
  .os-panel { padding: 8px; }
}

@media (prefers-reduced-motion: reduce) {
  .os-tab,
  .os-tab::after { transition: none; }
}
</style>
