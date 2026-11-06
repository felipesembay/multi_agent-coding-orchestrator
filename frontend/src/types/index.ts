export type Payload = Record<string, unknown>
export type RawEvent = {
  id?: number
  at: string
  stage: string
  payload: string
}
export type ParsedEvent = RawEvent & {
  data: Payload
  malformed: boolean
  raw: unknown
}
export type Run = {
  project_id?: string
  project_name?: string
  request_id?: string
  request_title?: string
  created_at?: string
  manager_status?: string
  supervisor_online?: boolean | null
  orphaned?: boolean
  error?: string | null
  configuration?: ExecutionConfiguration
  run_id: string
  repo: string | null
  worktree: string | null
  status: string
  started_at: string | null
  finished_at: string | null
  last_event: string | null
  duration_seconds: number | null
  task_count: number | null
  tests_passed: boolean | null
  current_stage: string | null
  attempts: number
}
export type RunPage = {
  items: Run[]
  total: number
  limit: number
  offset: number
}
export type RunDetail = Run & { events: RawEvent[] }
export type Overview = {
  total: number
  counts: Record<string, number>
  average_duration_seconds: number | null
  duration_sample_count: number
  activity: (RawEvent & { run_id: string })[]
}
export type Settings = {
  planner: string
  implementer: string
  reviewer: string
  planner_model: string | null
  implementer_model: string | null
  antigravity_default_model: string
  test_command: string | null
  database: string
  versions: Record<string, string | null>
}

// Validated projections of known payloads. Unknown fields remain in ParsedEvent.raw.
export type Task = {
  id: string | null
  title: string | null
  instructions: string | null
  acceptance: unknown[]
  tests: unknown[]
}
export type ReviewPayload = {
  task: string | null
  approved: boolean | null
  findings: unknown[]
  test_suggestions: unknown[]
  test_result: {
    passed: boolean | null
    output: string | null
    error: string | null
  }
}
export type ImplementationPayload = {
  task: string | null
  attempt: number | null
  output: string | null
}
export type StartedPayload = { repo: string | null; worktree: string | null }
export type FinishedPayload = { status: string | null; worktree: string | null }

export type Project = {
  id: string
  name: string
  description: string
  objectives: string
  repository_id: string
  repo_path: string
  state: 'active' | 'archived'
  created_at: string
  updated_at: string
  request_count?: number
}
export type ProjectRequest = {
  id: string
  project_id: string
  title: string
  content: string
  state: string
  created_at: string
}
export type ProjectInput = {
  name: string
  description: string
  objectives: string
  repo_path: string
  mode: 'existing' | 'create'
}
export type ProjectPolicy = {
  roots: { path: string; available: boolean }[]
  git_available: boolean
  preview_ttl_seconds: number
}
export type ProjectPreview = {
  preview_token: string
  project: ProjectInput
  actions: string[]
  expires_in_seconds: number
}

export type ExecutionConfiguration = {
  planner: string
  implementer: string
  reviewer: string
  planner_model: string | null
  implementer_model: string | null
  planner_fallback_model: string
  test_command: string
  max_attempts: number
  agent_timeout: number
  test_timeout: number
  worktree_base: string
}
export type ExecutionPreflight = {
  configuration: ExecutionConfiguration
  configuration_digest: string
  worker: { online: boolean; heartbeat: number | null }
  ready: boolean
  errors: string[]
}
export type StartRunResult = {
  run_id: string
  status: string
  project_id: string
  request_id: string
}
