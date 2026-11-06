import { useQuery } from '@tanstack/react-query'
import type { Project, ProjectPolicy, ProjectRequest, Run } from '../types'
import { request } from './api'

export function useProjects(interval: number) {
  return useQuery({
    queryKey: ['projects'],
    queryFn: ({ signal }) => request<Project[]>('/projects', signal),
    refetchInterval: interval || false,
  })
}
export function useProject(id: string) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: ({ signal }) =>
      request<Project>(`/projects/${encodeURIComponent(id)}`, signal),
    enabled: !!id,
  })
}
export function useProjectRequests(id: string, interval: number) {
  return useQuery({
    queryKey: ['project-requests', id],
    queryFn: ({ signal }) =>
      request<ProjectRequest[]>(
        `/projects/${encodeURIComponent(id)}/requests`,
        signal,
      ),
    enabled: !!id,
    refetchInterval: interval || false,
  })
}
export function useProjectRuns(id: string, interval: number) {
  return useQuery({
    queryKey: ['project-runs', id],
    queryFn: ({ signal }) =>
      request<Run[]>(`/projects/${encodeURIComponent(id)}/runs`, signal),
    enabled: !!id,
    refetchInterval: interval || false,
  })
}
export function useProjectPolicy() {
  return useQuery({
    queryKey: ['project-policy'],
    queryFn: ({ signal }) => request<ProjectPolicy>('/project-policy', signal),
    staleTime: 0,
  })
}
export async function mutate<T>(
  path: string,
  body: unknown,
  method = 'POST',
): Promise<T> {
  // Fetch for each write so a restarted API never leaves a stale token in storage.
  const session = await request<{ csrf_token: string }>('/session')
  const response = await fetch(`/api${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Orchestrator-CSRF': session.csrf_token,
    },
    body: JSON.stringify(body),
  })
  const data: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const detail =
      data && typeof data === 'object' && 'detail' in data
        ? data.detail
        : undefined
    throw new Error(
      typeof detail === 'string'
        ? detail
        : response.status === 422
          ? 'Verifique os campos obrigatórios e os limites de tamanho.'
          : `Não foi possível salvar (${response.status}).`,
    )
  }
  return data as T
}
