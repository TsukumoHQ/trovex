import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
    },
  },
  // The serverless api/ layer, build scripts, and the vitest suite run on Node.
  // They were previously unlinted — the security-sensitive lead-capture code among
  // them. Lint them with Node globals and the recommended ruleset.
  {
    files: ['api/**/*.js', 'scripts/**/*.mjs', 'test/**/*.js', '*.{js,mjs,ts}'],
    extends: [js.configs.recommended],
    languageOptions: {
      globals: { ...globals.node },
    },
  },
])
