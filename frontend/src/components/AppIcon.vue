<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })

const paths: Record<string, string[]> = {
  grid: ['M3.5 3.5h6v6h-6z M14.5 3.5h6v6h-6z M3.5 14.5h6v6h-6z M14.5 14.5h6v6h-6z'],
  home: ['m3 10 9-7 9 7', 'M5 9v11h5v-7h4v7h5V9'],
  upload: ['M12 15V3', 'm7 8 5-5 5 5', 'M4 14v6h16v-6'],
  sparkles: ['m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z', 'M20 2v4 M18 4h4'],
  package: ['m3 7 9-4 9 4v10l-9 4-9-4V7Z', 'm3 7 9 4 9-4 M12 11v10 M7.5 5l9 4v4'],
  messages: ['M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l1.5-4A8.5 8.5 0 1 1 21 11.5Z'],
  chart: ['M5 20V11 M12 20V4 M19 20V8'],
  settings: [
    'm9.2 3-.7 2.2-2 .9-2.1-.5-2.1 3.6 1.5 1.7v2.2l-1.5 1.7 2.1 3.6 2.1-.5 2 .9.7 2.2h4.2l.7-2.2 2-.9 2.1.5 2.1-3.6-1.5-1.7v-2.2l1.5-1.7-2.1-3.6-2.1.5-2-.9L13.4 3H9.2Z',
    'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z',
  ],
  chevron: ['m8 5 7 7-7 7'],
  menu: ['M4 6h16 M4 12h16 M4 18h16'],
  close: ['m6 6 12 12 M18 6 6 18'],
  arrow: ['M4 12h16 m-6-6 6 6-6 6'],
  check: ['m5 12 4 4L19 6'],
  file: ['M13 3H5v18h14V9l-6-6Z', 'M13 3v6h6 M8 13h8 M8 17h5'],
  wallet: ['M20 8V5H5a2 2 0 0 0 0 4h16v11H5a2 2 0 0 1-2-2V7', 'M21 12h-6v5h6 M17.5 14.5h.01'],
  clipboard: ['M9 4H5v17h14V4h-4', 'M9 2h6v5H9z M8 11h8 M8 15h6'],
  clock: ['M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z', 'M12 7v5l3 2'],
  inbox: ['M4 4h16l2 11v5H2v-5L4 4Z', 'M2 15h6l2 3h4l2-3h6'],
  refresh: ['M20 7a9 9 0 0 0-15-1L2 9 M2 3v6h6', 'M4 17a9 9 0 0 0 15 1l3-3 M22 21v-6h-6'],
  play: ['m8 4 12 8-12 8V4Z'],
  filter: ['M3 4h18l-7 8v7l-4 2v-9L3 4Z'],
  eye: ['M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z', 'M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z'],
  shield: ['m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z', 'm8 12 3 3 5-6'],
  receipt: ['M5 3h14v18l-3-2-4 2-4-2-3 2V3Z', 'M8 7h8 M8 11h8 M8 15h4'],
  edit: ['m15 4 5 5 M4 20l5-1L21 7l-5-5L4 14v6Z'],
  send: ['m22 2-7 20-4-9-9-4L22 2Z', 'M11 13 22 2'],
  calendar: ['M4 5h16v16H4z M8 3v4 M16 3v4 M4 10h16 M8 14h2 M14 14h2 M8 17h2'],
  leaf: ['M20 3c-9 0-16 3-16 10a7 7 0 0 0 7 7c7 0 9-8 9-17Z', 'M4 20 16 8'],
}
</script>

<template>
  <svg
    class="app-icon"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.7"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="(path, index) in paths[name] ?? paths.grid" :key="index" :d="path" />
  </svg>
</template>
