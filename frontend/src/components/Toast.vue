<template>
  <div class="toast-wrap">
    <transition-group name="toast">
      <div v-for="t in toastState.items" :key="t.id" class="toast" :class="t.type">
        {{ t.text }}
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { toastState } from '../stores/toast'
</script>

<style scoped>
.toast-wrap {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  align-items: center;
}
.toast {
  padding: 11px 22px;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.15);
  min-width: 200px;
  text-align: center;
}
.toast.success {
  background: #1bbf73;
}
.toast.error {
  background: #f5564a;
}
.toast.info {
  background: #2b8fff;
}
.toast-enter-from,
.toast-leave-to {
  opacity: 0;
  transform: translateY(-12px);
}
.toast-enter-active,
.toast-leave-active {
  transition: all 0.25s;
}
</style>
