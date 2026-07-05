import 'dotenv/config'
import { start } from './bootstrap/startup'

start().catch(err => {
  console.error('[ATHENA] Fatal startup error:', err)
  process.exit(1)
})
