// ESLint 扁平配置（ESLint 9+）
// Vue 3 + TypeScript 编码规范
import pluginVue from 'eslint-plugin-vue';
import tsParser from '@typescript-eslint/parser';
import tsPlugin from '@typescript-eslint/eslint-plugin';

export default [
  {
    ignores: [
      'dist/**',
      'node_modules/**',
      '*.js',
      '*.cjs',
      '!vite.config.ts',
    ],
  },
  // Vue 3 推荐规则
  ...pluginVue.configs['flat/recommended'],
  // TypeScript 规则
  {
    files: ['**/*.ts', '**/*.tsx', '**/*.vue'],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 'latest',
        sourceType: 'module',
      },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
    },
    rules: {
      // 命名规范：驼峰命名
      camelcase: ['warn', { properties: 'always' }],
      // 函数应有注释
      'require-jsdoc': [
        'warn',
        {
          require: {
            FunctionDeclaration: true,
            MethodDefinition: true,
            ClassDeclaration: true,
            ArrowFunctionExpression: false,
          },
        },
      ],
      // TypeScript 推荐规则
      ...tsPlugin.configs.recommended.rules,
      // 允许 any（实际项目中适当放宽）
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },
  // Vue 特定规则
  {
    files: ['**/*.vue'],
    rules: {
      'vue/multi-word-component-names': 'off',
      'vue/max-attributes-per-line': ['warn', { singleline: 3, multiline: 1 }],
      'vue/singleline-html-element-content-newline': 'off',
      'vue/html-self-closing': ['warn', { html: { void: 'always' } }],
      'vue/component-tags-order': ['warn', { order: ['template', 'script', 'style'] }],
      'vue/attributes-order': 'warn',
      'vue/no-v-html': 'off',
    },
  },
];
