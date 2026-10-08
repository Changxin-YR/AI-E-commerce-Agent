import js from '@eslint/js'
import tseslint from 'typescript-eslint'
import vue from 'eslint-plugin-vue'
import playwright from 'eslint-plugin-playwright'
import vitest from '@vitest/eslint-plugin'
import skipFormatting from 'eslint-config-prettier/flat'

export default tseslint.config(
  { ignores: ['dist/**', 'coverage/**', 'playwright-report/**', 'test-results/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs['flat/essential'],
  {
    files: ['**/*.vue'],
    languageOptions: { parserOptions: { parser: tseslint.parser } },
    // TypeScript checks undefined names in script setup, including DOM globals.
    rules: { 'no-undef': 'off' },
  },
  { ...playwright.configs['flat/recommended'], files: ['e2e/**/*.spec.ts'] },
  { ...vitest.configs.recommended, files: ['src/**/__tests__/*.spec.ts'] },
  skipFormatting,
)
