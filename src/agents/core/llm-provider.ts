import OpenAI from 'openai'
import Anthropic from '@anthropic-ai/sdk'
import Groq from 'groq-sdk'
import { getConfig } from '../../shared/infrastructure/config/app-config'
import type { AgentConfig } from './agent-types'

export interface LLMMessage {
  role: 'system' | 'user' | 'assistant'
  content: string
}

export interface LLMResponse {
  content: string
  model: string
  usage?: { promptTokens: number; completionTokens: number; totalTokens: number }
  finishReason: string
}

export interface LLMProvider {
  complete(messages: LLMMessage[], options?: { temperature?: number; maxTokens?: number }): Promise<LLMResponse>
  embedding(text: string): Promise<number[]>
}

function createProvider(config: AgentConfig): LLMProvider {
  const appConfig = getConfig()
  const model = config.modelName || appConfig.LLM_MODEL

  switch (config.modelProvider) {
    case 'openai': {
      const client = new OpenAI({ apiKey: appConfig.OPENAI_API_KEY || 'sk-placeholder' })
      return {
        async complete(messages, options) {
          const resp = await client.chat.completions.create({
            model,
            messages: messages.map(m => ({ role: m.role as 'system' | 'user' | 'assistant', content: m.content })),
            temperature: options?.temperature ?? config.temperature ?? 0.3,
            max_tokens: options?.maxTokens ?? config.maxTokens ?? 4096,
          })
          return {
            content: resp.choices[0]?.message?.content ?? '',
            model: resp.model,
            usage: resp.usage ? { promptTokens: resp.usage.prompt_tokens, completionTokens: resp.usage.completion_tokens, totalTokens: resp.usage.total_tokens } : undefined,
            finishReason: resp.choices[0]?.finish_reason ?? 'stop',
          }
        },
        async embedding(text) {
          const resp = await client.embeddings.create({ model: 'text-embedding-3-small', input: text })
          return resp.data[0]?.embedding ?? new Array(1536).fill(0) as number[]
        },
      }
    }
    case 'anthropic': {
      const client = new Anthropic({ apiKey: appConfig.ANTHROPIC_API_KEY || 'sk-ant-placeholder' })
      return {
        async complete(messages, options) {
          const systemMsg = messages.find(m => m.role === 'system')
          const userMsgs = messages.filter(m => m.role !== 'system')
          const resp = await client.messages.create({
            model,
            system: systemMsg?.content,
            messages: userMsgs.map(m => ({ role: 'user' as const, content: m.content })),
            max_tokens: options?.maxTokens ?? config.maxTokens ?? 4096,
          })
          const textBlock = resp.content[0]
          return {
            content: textBlock?.type === 'text' ? textBlock.text : '',
            model: resp.model,
            usage: resp.usage ? { promptTokens: resp.usage.input_tokens, completionTokens: resp.usage.output_tokens, totalTokens: resp.usage.input_tokens + resp.usage.output_tokens } : undefined,
            finishReason: resp.stop_reason ?? 'end_turn',
          }
        },
        async embedding(_text) {
          return new Array(1536).fill(0) as number[]
        },
      }
    }
    case 'deepseek': {
      const client = new OpenAI({
        apiKey: appConfig.DEEPSEEK_API_KEY || 'sk-placeholder',
        baseURL: 'https://api.deepseek.com',
      })
      return {
        async complete(messages, options) {
          const resp = await client.chat.completions.create({
            model: model || 'deepseek-chat',
            messages: messages.map(m => ({ role: m.role as 'system' | 'user' | 'assistant', content: m.content })),
            temperature: options?.temperature ?? config.temperature ?? 0.3,
            max_tokens: options?.maxTokens ?? config.maxTokens ?? 4096,
          })
          return {
            content: resp.choices[0]?.message?.content ?? '',
            model: resp.model,
            usage: resp.usage ? { promptTokens: resp.usage.prompt_tokens, completionTokens: resp.usage.completion_tokens, totalTokens: resp.usage.total_tokens } : undefined,
            finishReason: resp.choices[0]?.finish_reason ?? 'stop',
          }
        },
        async embedding(_text) {
          return new Array(1536).fill(0) as number[]
        },
      }
    }
    case 'groq': {
      const client = new Groq({ apiKey: appConfig.GROQ_API_KEY || 'gsk-placeholder' })
      return {
        async complete(messages, options) {
          const resp = await client.chat.completions.create({
            model,
            messages: messages.map(m => ({ role: m.role as 'system' | 'user' | 'assistant', content: m.content })),
            temperature: options?.temperature ?? config.temperature ?? 0.3,
            max_tokens: options?.maxTokens ?? config.maxTokens ?? 4096,
          })
          return {
            content: resp.choices[0]?.message?.content ?? '',
            model: resp.model,
            usage: resp.usage ? { promptTokens: resp.usage.prompt_tokens, completionTokens: resp.usage.completion_tokens, totalTokens: resp.usage.total_tokens } : undefined,
            finishReason: resp.choices[0]?.finish_reason ?? 'stop',
          }
        },
        async embedding(_text) {
          return new Array(1536).fill(0) as number[]
        },
      }
    }
    default: {
      const client = new OpenAI({ apiKey: appConfig.OPENAI_API_KEY || 'sk-placeholder' })
      return {
        async complete(messages, options) {
          const resp = await client.chat.completions.create({
            model,
            messages: messages.map(m => ({ role: m.role as 'system' | 'user' | 'assistant', content: m.content })),
            temperature: options?.temperature ?? config.temperature ?? 0.3,
            max_tokens: options?.maxTokens ?? config.maxTokens ?? 4096,
          })
          return {
            content: resp.choices[0]?.message?.content ?? '',
            model: resp.model,
            finishReason: resp.choices[0]?.finish_reason ?? 'stop',
          }
        },
        async embedding(text) {
          const resp = await client.embeddings.create({ model: 'text-embedding-3-small', input: text })
          return resp.data[0]?.embedding ?? new Array(1536).fill(0) as number[]
        },
      }
    }
  }
}

export function createLLMProvider(config: AgentConfig): LLMProvider {
  return createProvider(config)
}
