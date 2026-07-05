export interface PromptTemplate {
  readonly name: string
  readonly version: string
  readonly system: string
  readonly context: string
  readonly tools: string
  readonly format: string
}

export interface PromptVariables {
  readonly [key: string]: string | number | boolean | undefined
}

export class PromptManager {
  private templates = new Map<string, PromptTemplate>()

  register(template: PromptTemplate): void {
    this.templates.set(`${template.name}@${template.version}`, template)
    this.templates.set(template.name, template)
  }

  get(name: string, version?: string): PromptTemplate | undefined {
    if (version) return this.templates.get(`${name}@${version}`)
    return this.templates.get(name)
  }

  resolve(template: PromptTemplate, variables: PromptVariables): string {
    const parts: string[] = []
    if (template.system) parts.push(replace(template.system, variables))
    if (template.context) parts.push(replace(template.context, variables))
    if (template.tools) parts.push(replace(template.tools, variables))
    if (template.format) parts.push(replace(template.format, variables))
    return parts.join('\n\n')
  }
}

function replace(text: string, vars: PromptVariables): string {
  return text.replace(/\{\{(\w+)\}\}/g, (_, key) => String(vars[key] ?? `{{${key}}}`))
}
