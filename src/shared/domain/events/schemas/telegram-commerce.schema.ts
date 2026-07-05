import { z } from 'zod'

export const ConversationStartedPayload = z.object({
  chatId: z.string().min(1),
  telegramUserId: z.string().min(1),
  username: z.string().optional(),
  firstName: z.string().optional(),
  languageCode: z.string().optional(),
  entryPoint: z.enum(['direct', 'inline_query', 'group', 'referral']).optional(),
  startedAt: z.string().datetime(),
})

export const OrderConfirmedViaChatPayload = z.object({
  chatOrderId: z.string().min(1),
  telegramUserId: z.string().min(1),
  chatId: z.string().min(1),
  items: z.array(z.object({
    sku: z.string().min(1),
    quantity: z.number().int().positive(),
    unitPrice: z.number().nonnegative(),
    total: z.number().nonnegative().optional(),
  })).min(1),
  shippingAddress: z.object({
    recipientName: z.string().min(1),
    street: z.string().optional(),
    number: z.string().optional(),
    neighborhood: z.string().optional(),
    city: z.string().min(1),
    state: z.string().min(1),
    zipCode: z.string().min(1),
  }),
  totals: z.object({
    subtotal: z.number().nonnegative(),
    shipping: z.number().optional(),
    discount: z.number().optional(),
    grandTotal: z.number().nonnegative(),
    currency: z.string().default('BRL'),
  }),
  confirmedAt: z.string().datetime(),
})

export const PaymentCompletedPayload = z.object({
  paymentId: z.string().min(1),
  chatOrderId: z.string().min(1),
  amount: z.number().nonnegative(),
  method: z.enum(['pix', 'credit_card', 'boleto', 'wallet']),
  installments: z.number().int().positive().optional(),
  transactionId: z.string().optional(),
  completedAt: z.string().datetime(),
})
