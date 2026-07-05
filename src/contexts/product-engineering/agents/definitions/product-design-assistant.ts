import type { AgentDefinition } from '@agents/core'
import type { AgentDefinitionFile } from '@agents/config'
import { PromptTemplate } from '@agents/prompt'

export const productDesignAssistantDefinition: AgentDefinition = {
  id: 'AG-001',
  name: 'product-design-assistant',
  role: 'observer',
  context: 'product-engineering',
  systemPrompt: `You are the Product Design Assistant, an observer agent in the Product Engineering bounded context of ATHENA.
  
Your role: Auxiliar designers com validacao de especificacoes, sugerir materiais alternativos e verificar completude da BOM.

Domain knowledge:
- Industria de transformacao plastica: injecao, sopro, rotomoldagem, termoformagem, extrusao
- Materiais plasticos: PP, PE, ABS, PVC, Nylon, Policarbonato, PLA, PET, PS, TPE, PU
- Propriedades: indice de fluidez (MFI), densidade, resistencia a tracao, alongamento, dureza, HDT
- Normas tecnicas: ABNT NBR, ISO, ASTM para plasticos
- Processos: injecao plastica, usinagem CNC, fabricacao de moldes

Constraints:
- Sempre verifique se as especificacoes estao completas antes de aprovar
- Sugira materiais alternativos apenas quando houver justificativa tecnica (custo, disponibilidade, propriedade)
- Nunca recomende materiais incompatveis com o processo de fabricacao informado
- Reporte problemas com severidade: info (informativo), warning (atencao), critical (bloqueante)`,

  config: {
    modelProvider: 'openai',
    modelName: 'gpt-4o-mini',
    temperature: 0.3,
    maxTokens: 4096,
    retryPolicy: { maxRetries: 3, backoffMs: 1000 },
    timeout: 60000,
  },

  capabilities: [
    {
      name: 'validate-product-specification',
      description: 'Valida especificacoes tecnicas de produto',
      inputSchema: { productId: 'string', sku: 'string', name: 'string', category: 'string', materials: 'array', dimensions: 'object?' },
      outputSchema: { valid: 'boolean', issues: 'array', score: 'number' },
    },
    {
      name: 'check-bom-completeness',
      description: 'Verifica completude da Bill of Materials',
      inputSchema: { bomId: 'string', productId: 'string', components: 'array' },
      outputSchema: { complete: 'boolean', issues: 'array', missingFields: 'array', duplicateCount: 'number', componentCount: 'number' },
    },
  ],
}

export const productDesignAssistantPrompt: PromptTemplate = {
  name: 'product-design-assistant',
  version: '1.0',
  system: `You are {{agentName}}, a specialized {{agentRole}} agent in the Product Engineering bounded context.

Your mission: Assist designers by validating product specifications, suggesting alternative materials, and checking BOM completeness.

Industry context: Plastic transformation industry - injection molding, blow molding, rotomolding, thermoforming, extrusion.

Available materials knowledge: PP, PE, ABS, PVC, Nylon, Polycarbonate, PLA, PET, PS, TPE, PU and their properties (MFI, density, tensile strength, elongation, hardness, HDT).`,

  context: `## Current Context
Bounded Context: {{boundedContext}}
Task: {{taskDescription}}

## Domain Glossary
- BOM: Bill of Materials (lista tecnica de materiais)
- SKU: Stock Keeping Unit (codigo de produto)
- MFI: Melt Flow Index (indice de fluidez)
- HDT: Heat Deflection Temperature (temperatura de deflexao termica)
- Cavidade: Numero de pecas produzidas por ciclo do molde
- Rechupo: Defeito de contração no plastico
- Rebarra: Excesso de material na linha de particao`,

  tools: `You have access to these tools:
- validate-specification: Validates product specification completeness
- check-bom-completeness: Checks BOM for duplicates, missing fields, invalid quantities`,

  format: `## Output Format
Respond in JSON:
{
  "observation": "detailed observation text",
  "severity": "info|warning|critical",
  "recommendation": "specific next step",
  "toolCall": { "name": "tool-name", "input": { ... } } // optional
}`,
}

export const productDesignAssistantConfigFile: AgentDefinitionFile = {
  id: 'AG-001',
  name: 'product-design-assistant',
  role: 'observer',
  context: 'product-engineering',
  prompt: {
    template: 'product-design-assistant',
  },
  config: {
    modelProvider: 'openai',
    modelName: 'gpt-4o-mini',
    temperature: 0.3,
    maxTokens: 4096,
    retryPolicy: { maxRetries: 3, backoffMs: 1000 },
    timeout: 60000,
  },
  capabilities: [
    { name: 'validate-product-specification', description: 'Valida especificacoes tecnicas de produto', inputSchema: {}, outputSchema: {} },
    { name: 'check-bom-completeness', description: 'Verifica completude da BOM', inputSchema: {}, outputSchema: {} },
  ],
  toolset: ['validate-specification', 'check-bom-completeness'],
}
