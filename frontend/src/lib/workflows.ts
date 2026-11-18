import type { ProviderConfig, WorkflowBinding, WorkflowStep } from '../types'

export function ownBinding(
  bindings: Record<string, WorkflowBinding> | undefined,
  stepId: string,
) {
  return bindings && Object.hasOwn(bindings, stepId)
    ? bindings[stepId]
    : undefined
}

export function permissionFor(
  step: WorkflowStep,
): WorkflowBinding['permission'] {
  return step.type === 'implement' || step.requires?.includes('code_edit')
    ? 'workspace_write'
    : 'read_only'
}

export function compatibleProvider(step: WorkflowStep, config: ProviderConfig) {
  const required = new Set(['text', ...(step.requires ?? [])])
  const base: Record<string, string> = {
    plan: 'planning',
    implement: 'code_edit',
    review: 'review',
    document: 'text',
  }
  required.add(base[step.type])
  return (
    config.enabled &&
    config.available &&
    config.permission_modes.includes(permissionFor(step)) &&
    [...required].every((capability) =>
      config.capabilities.includes(capability),
    ) &&
    (!required.has('code_edit') ||
      (config.kind === 'agent_runtime' && config.verified))
  )
}
