import js from '@eslint/js';
import globals from 'globals';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import eslintReact from '@eslint-react/eslint-plugin';
import reactHooks from 'eslint-plugin-react-hooks';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import importX from 'eslint-plugin-import-x';
import prettierRecommended from 'eslint-plugin-prettier/recommended';

const reactRecommended = eslintReact.configs['recommended-typescript'];

// Flat config (ESLint 9+). Replaces the legacy .eslintrc. React linting is
// provided by @eslint-react/eslint-plugin — eslint-plugin-react / airbnb are
// not compatible with ESLint 10.
export default [
  {
    ignores: ['build/**', 'dist/**', 'coverage/**', 'node_modules/**', 'notebooks/**'],
  },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: 'module',
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.es2021 },
    },
    settings: {
      ...reactRecommended.settings,
      'react-x': { ...reactRecommended.settings['react-x'], version: '19.0' },
      'import-x/resolver': {
        typescript: true,
        node: {
          paths: ['.'],
          extensions: ['.js', '.jsx', '.ts', '.tsx'],
        },
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      '@eslint-react': eslintReact,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
      'import-x': importX,
    },
    rules: {
      ...tsPlugin.configs['eslint-recommended'].overrides[0].rules,
      ...tsPlugin.configs.recommended.rules,
      ...reactRecommended.rules,
      ...jsxA11y.flatConfigs.recommended.rules,
      ...importX.flatConfigs.recommended.rules,
      'react-hooks/rules-of-hooks': 'error',
      // Project overrides — carried over from the legacy .eslintrc.
      '@eslint-react/exhaustive-deps': 'off',
      'jsx-a11y/anchor-is-valid': 'off',
      'no-console': 'off',
      'no-plusplus': 'off',
      'no-unused-expressions': 'error',
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-expressions': 'off',
      'import-x/extensions': [
        'error',
        'ignorePackages',
        { js: 'never', jsx: 'never', ts: 'never', tsx: 'never' },
      ],
    },
  },
  {
    files: ['**/__tests__/**/*.tsx', '**/*.test.tsx', 'src/setupTests.ts'],
    languageOptions: {
      globals: { ...globals.jest },
    },
    rules: {
      'import-x/no-extraneous-dependencies': ['error', { devDependencies: true }],
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
  prettierRecommended,
];
