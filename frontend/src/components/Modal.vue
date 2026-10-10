<template>
  <transition name="fade">
    <div v-if="modelValue" class="modal-mask" @click.self="$emit('update:modelValue', false)">
      <div class="modal">
        <div class="modal-header">{{ title }}</div>
        <div class="modal-body">
          <slot />
        </div>
        <div class="modal-footer">
          <button class="btn btn-ghost" @click="$emit('update:modelValue', false)">取消</button>
          <button class="btn btn-primary" :disabled="loading" @click="$emit('confirm')">
            {{ loading ? '处理中…' : confirmText }}
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
// 通用弹窗组件，通过 v-model 控制显隐
defineProps({
  modelValue: Boolean,
  title: String,
  confirmText: { type: String, default: '确定' },
  loading: Boolean
})
defineEmits(['update:modelValue', 'confirm'])
</script>

<style scoped>
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s;
}
</style>
