import type { Config } from 'jest'

const config: Config = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  roots: ['<rootDir>/tests'],
  moduleNameMapper: {
    '^@shared/(.*)$': '<rootDir>/src/shared/$1',
    '^@contexts/(.*)$': '<rootDir>/src/contexts/$1',
    '^@agents/(.*)$': '<rootDir>/src/agents/$1',
  },
  collectCoverageFrom: [
    'src/**/*.ts',
    '!src/**/index.ts',
    '!src/bootstrap/**',
  ],
  coverageThreshold: {
    global: {
      statements: 80,
      branches: 70,
      functions: 80,
      lines: 80,
    },
  },
  testMatch: ['**/tests/**/*.test.ts', '**/tests/**/*.spec.ts'],
  testPathIgnorePatterns: [
    '<rootDir>/tests/unit/agents/product-design-assistant.test.ts',
    '<rootDir>/tests/unit/shared/product-design-assistant.test.ts',
    '<rootDir>/tests/unit/agents/ag001-product-design-assistant.test.ts',
    '<rootDir>/tests/unit/agents/smoke.test.ts',
    '<rootDir>/tests/unit/agents/static-import.test.ts',
    '<rootDir>/tests/unit/agents/agent-infrastructure.test.ts',
    '<rootDir>/tests/unit/contexts/domain-entities.test.ts',
    '<rootDir>/tests/integration/',
  ],
}

export default config
