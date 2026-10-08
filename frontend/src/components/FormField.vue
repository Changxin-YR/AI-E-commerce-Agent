<script setup lang="ts">
defineProps<{ label: string; forId: string; hint?: string; wide?: boolean }>()
</script>
<template>
  <div class="form-field" :class="{ wide }">
    <label :for="forId">{{ label }}</label
    ><slot /><small v-if="hint">{{ hint }}</small>
  </div>
</template>
