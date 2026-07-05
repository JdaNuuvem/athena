import { defineConfig } from 'prisma/config'

export default defineConfig({
  datasources: {
    db: {
      connectionString: `postgresql://athena:athena@localhost:5433/athena`,
    },
  },
  migrate: {
    datasource: 'db',
  },
})
