<template>
  <div class="whale-insight">
    <button class="whale-summon-btn" type="button" @click="summon" :aria-expanded="visible">
      <img src="/assets/whale-summon/idle/00.png" alt="" class="btn-whale-icon" />
      <span>问问鲸宝</span>
    </button>

    <div v-if="visible" class="whale-stage">
      <div class="whale-character">
        <img :src="currentFrame" alt="鲸宝" class="whale-sprite" />
      </div>
      <div class="whale-speech">
        <div class="speech-content">
          <slot />
        </div>
        <button class="speech-dismiss" @click="dismiss" aria-label="关闭">收起</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted } from 'vue'

const visible = ref(false)
const currentFrame = ref('/assets/whale-summon/idle/00.png')

const WAVING = Array.from({ length: 4 }, (_, i) => `/assets/whale-summon/waving/${String(i).padStart(2, '0')}.png`)
const IDLE = Array.from({ length: 6 }, (_, i) => `/assets/whale-summon/idle/${String(i).padStart(2, '0')}.png`)

let timer = null

function playFrames(frames, durations, onDone) {
  clearTimeout(timer)
  let i = 0
  const next = () => {
    currentFrame.value = frames[i]
    const delay = Array.isArray(durations) ? durations[i] : durations
    i++
    if (i < frames.length) timer = setTimeout(next, delay)
    else if (onDone) timer = setTimeout(onDone, delay)
  }
  next()
}

function startIdle() {
  const durations = [280, 110, 110, 140, 140, 320]
  let i = 0
  const next = () => {
    currentFrame.value = IDLE[i]
    timer = setTimeout(next, durations[i])
    i = (i + 1) % IDLE.length
  }
  clearTimeout(timer)
  next()
}

function summon() {
  if (visible.value) { dismiss(); return }
  visible.value = true
  playFrames(WAVING, 150, startIdle)
}

function dismiss() {
  clearTimeout(timer)
  visible.value = false
  currentFrame.value = IDLE[0]
}

onUnmounted(() => clearTimeout(timer))
</script>

<style scoped>
.whale-insight {
  margin: 1.5rem 0;
}

.whale-summon-btn {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 16px 7px 8px;
  border: 1px solid color-mix(in srgb, var(--vp-c-text-1) 12%, transparent);
  border-radius: 999px;
  background: var(--vp-c-bg-soft);
  cursor: pointer;
  font: inherit;
  font-size: 0.84rem;
  font-weight: 550;
  color: var(--vp-c-text-2);
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;
}
.whale-summon-btn:hover {
  border-color: rgba(100, 180, 220, 0.5);
  box-shadow: 0 3px 14px rgba(100, 180, 220, 0.18);
  transform: translateY(-1px);
}
.btn-whale-icon {
  width: 26px;
  height: 26px;
  image-rendering: pixelated;
}

.whale-stage {
  display: flex;
  align-items: flex-start;
  gap: 0.8rem;
  margin-top: 0.8rem;
  animation: stageIn 0.35s cubic-bezier(0.2, 0.9, 0.3, 1.2);
}

.whale-character {
  flex-shrink: 0;
}
.whale-sprite {
  width: 72px;
  height: auto;
  image-rendering: pixelated;
  filter: drop-shadow(0 6px 12px rgba(53, 112, 164, 0.2));
  animation: whaleBouncein 0.4s cubic-bezier(0.2, 0.9, 0.3, 1.3);
}

.whale-speech {
  flex: 1;
  min-width: 0;
  padding: 0.8rem 1rem;
  border: 1px solid rgba(100, 180, 220, 0.28);
  border-radius: 12px;
  background: color-mix(in srgb, rgba(100, 180, 220, 0.05), var(--vp-c-bg));
  position: relative;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--vp-c-text-1);
  animation: bubbleIn 0.3s 0.1s ease-out both;
}
.whale-speech::before {
  content: '';
  position: absolute;
  left: -7px;
  top: 18px;
  width: 12px;
  height: 12px;
  background: inherit;
  border-left: 1px solid rgba(100, 180, 220, 0.28);
  border-bottom: 1px solid rgba(100, 180, 220, 0.28);
  transform: rotate(45deg);
}

.speech-content :deep(p) {
  margin: 0;
}
.speech-dismiss {
  display: inline-block;
  margin-top: 0.5rem;
  border: none;
  background: none;
  font: inherit;
  font-size: 0.78rem;
  color: var(--vp-c-text-3);
  cursor: pointer;
  padding: 2px 0;
}
.speech-dismiss:hover {
  color: var(--vp-c-text-2);
}

@keyframes stageIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: none; }
}
@keyframes whaleBouncein {
  0% { opacity: 0; transform: scale(0.3) translateY(20px); }
  60% { opacity: 1; transform: scale(1.1) translateY(-4px); }
  100% { transform: scale(1) translateY(0); }
}
@keyframes bubbleIn {
  from { opacity: 0; transform: translateX(-6px) scale(0.96); }
  to { opacity: 1; transform: none; }
}

@media (max-width: 640px) {
  .whale-sprite { width: 54px; }
  .whale-stage { gap: 0.5rem; }
}
</style>
