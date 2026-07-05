import nodemailer from 'nodemailer'
import type { Transporter } from 'nodemailer'

const isDev = process.env['NODE_ENV'] === 'development'

export interface EmailConfig {
  host: string
  port: number
  secure: boolean
  user: string
  pass: string
  from: string
}

export interface EmailMessage {
  to: string | string[]
  subject: string
  html: string
  cc?: string | string[]
  attachments?: Array<{ filename: string; content: string | Buffer; contentType?: string }>
}

export class EmailSender {
  private transporter: Transporter | null = null
  private config: EmailConfig | null = null

  constructor() {
    const host = process.env['SMTP_HOST']
    const port = process.env['SMTP_PORT']
    const user = process.env['SMTP_USER']
    const pass = process.env['SMTP_PASS']
    const from = process.env['SMTP_FROM'] ?? 'athena@example.com'

    if (host && port && user && pass) {
      this.config = {
        host,
        port: Number(port),
        secure: Number(port) === 465,
        user,
        pass,
        from,
      }
      this.transporter = nodemailer.createTransport({
        host,
        port: Number(port),
        secure: Number(port) === 465,
        auth: { user, pass },
      })
    }
  }

  get isConfigured(): boolean {
    if (isDev) return true
    return this.transporter !== null
  }

  async send(msg: EmailMessage): Promise<{ messageId: string } | null> {
    if (!this.transporter || !this.config) {
      if (isDev) {
        console.log('[Email] Sandbox mode — email logged:', { to: msg.to, subject: msg.subject })
        return { messageId: '<sandbox@athena.dev>' }
      }
      console.warn('[Email] SMTP not configured — email not sent')
      return null
    }
    try {
      const info = await this.transporter.sendMail({
        from: this.config.from,
        to: Array.isArray(msg.to) ? msg.to.join(', ') : msg.to,
        cc: msg.cc ? (Array.isArray(msg.cc) ? msg.cc.join(', ') : msg.cc) : undefined,
        subject: msg.subject,
        html: msg.html,
        attachments: msg.attachments,
      })
      return { messageId: info.messageId }
    } catch (err) {
      console.error('[Email] Send failed:', err)
      return null
    }
  }

  async sendAlert(to: string, title: string, body: string, severity: 'info' | 'warning' | 'critical' | 'success'): Promise<void> {
    const colors: Record<string, string> = { info: '#3b82f6', warning: '#f59e0b', critical: '#ef4444', success: '#22c55e' }
    const icons: Record<string, string> = { info: 'ℹ️', warning: '⚠️', critical: '🚨', success: '✅' }
    await this.send({
      to,
      subject: `[ATHENA] ${icons[severity]} ${title}`,
      html: `
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden;">
          <div style="background: ${colors[severity]}; padding: 16px; color: white;">
            <h2 style="margin: 0;">${icons[severity]} ${title}</h2>
          </div>
          <div style="padding: 16px; color: #374151; line-height: 1.6;">
            ${body.replace(/\n/g, '<br>')}
          </div>
          <div style="background: #f9fafb; padding: 12px; text-align: center; color: #9ca3af; font-size: 12px;">
            ATHENA Intelligence System — ${new Date().toLocaleDateString('pt-BR')}
          </div>
        </div>
      `,
    })
  }

  async sendDailyDigest(to: string, metrics: Array<{ label: string; value: string; change: string; trend: 'up' | 'down' | 'stable' }>): Promise<void> {
    const rows = metrics.map(m => {
      const color = m.trend === 'up' ? '#22c55e' : m.trend === 'down' ? '#ef4444' : '#6b7280'
      const arrow = m.trend === 'up' ? '↑' : m.trend === 'down' ? '↓' : '→'
      return `<tr><td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">${m.label}</td><td style="padding: 8px; border-bottom: 1px solid #e5e7eb; font-weight: bold;">${m.value}</td><td style="padding: 8px; border-bottom: 1px solid #e5e7eb; color: ${color};">${arrow} ${m.change}</td></tr>`
    }).join('')

    await this.send({
      to,
      subject: `📊 ATHENA Daily Digest — ${new Date().toLocaleDateString('pt-BR')}`,
      html: `
        <div style="font-family: sans-serif; max-width: 600px; margin: 0 auto;">
          <h2>📊 Resumo Diário</h2>
          <table style="width: 100%; border-collapse: collapse;">${rows}</table>
          <p style="color: #9ca3af; font-size: 12px; margin-top: 16px;">Gerado automaticamente pelo ATHENA Intelligence System</p>
        </div>
      `,
    })
  }

  async verifyConnection(): Promise<boolean> {
    if (!this.transporter) return isDev
    try {
      await this.transporter.verify()
      return true
    } catch {
      return false
    }
  }
}

export const emailSender = new EmailSender()
