import { ToolDefinition } from '../tools/tool-registry'
import { PromptManager, PromptTemplate, PromptVariables } from './prompt-manager'

export interface PromptContext {
  readonly agentName: string
  readonly agentRole: string
  readonly boundedContext: string
  readonly conversationHistory?: Array<{ role: string; content: string }>
  readonly taskDescription?: string
  readonly domainGlossary: Record<string, string>
}

export interface CompiledPrompt {
  readonly system: string
  readonly context: string
  readonly tools: string
  readonly format: string
  readonly full: string
}

export class PromptBuilder {
  constructor(private promptManager: PromptManager) {}

  build(templateName: string, ctx: PromptContext, tools: ToolDefinition[], variables?: PromptVariables): CompiledPrompt {
    const template = this.promptManager.get(templateName) ?? this.defaultTemplate(ctx)

    const mergedVars: PromptVariables = {
      agentName: ctx.agentName,
      agentRole: ctx.agentRole,
      boundedContext: ctx.boundedContext,
      taskDescription: ctx.taskDescription ?? '',
      ...variables,
    }

    const system = this.resolveSection(template.system, mergedVars, ctx)
    const context = this.resolveSection(template.context, mergedVars, ctx)
    const toolsSection = this.buildToolsSection(tools)
    const format = this.resolveSection(template.format, mergedVars, ctx)

    return {
      system,
      context,
      tools: toolsSection,
      format,
      full: [system, context, toolsSection, format].filter(Boolean).join('\n\n'),
    }
  }

  private resolveSection(section: string, vars: PromptVariables, ctx: PromptContext): string {
    return section.replace(/\{\{(\w+)\}\}/g, (_, key) => String(vars[key] ?? `{{${key}}}`))
  }

  private buildToolsSection(tools: ToolDefinition[]): string {
    if (!tools.length) return ''
    const list = tools.map(t => `- ${t.name}: ${t.description}`).join('\n')
    return `## Available Tools\n\n${list}\n\nTo invoke a tool, respond with:\n{ "tool": "<name>", "input": { ... } }`
  }

  private defaultTemplate(ctx: PromptContext): PromptTemplate {
    return {
      name: 'default',
      version: '1.0',
      system: `You are {{agentName}}, a specialized {{agentRole}} agent in the {{boundedContext}} bounded context.`,
      context: `Current task: {{taskDescription}}`,
      tools: '',
      format: 'Respond in JSON format: { "observation": "...", "severity": "info|warning|critical", "recommendation": "..." }',
    }
  }
}
