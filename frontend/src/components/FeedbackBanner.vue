<script setup lang="ts">
defineProps<{ message: string; kind?: 'error' | 'success' | 'info' }>()
</script>
<template>
  <p
    v-if="message"
    class="feedback"
    :class="kind ?? 'error'"
    :role="kind === 'error' || !kind ? 'alert' : 'status'"
  >
    {{ message }}
  </p>
</template>
