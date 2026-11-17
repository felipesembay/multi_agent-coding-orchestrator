import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import { Button } from '../components/ui/button'
import { mutate } from '../lib/projects'
import type { Project } from '../types'

export function DeleteProject({
  project,
  busy,
  onClose,
}: {
  project: Project
  busy: boolean
  onClose: () => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [name, setName] = useState('')
  const cache = useQueryClient(),
    navigate = useNavigate()
  const remove = useMutation({
    mutationFn: () =>
      mutate<{ deleted: boolean }>(
        `/projects/${encodeURIComponent(project.id)}`,
        { confirmed: true, project_name: name },
        'DELETE',
      ),
    onSuccess: async () => {
      await cache.invalidateQueries({ queryKey: ['projects'] })
      navigate('/', {
        state: {
          notice:
            'Projeto excluído da interface. Arquivos e histórico de execuções preservados.',
        },
      })
      for (const key of [
        'project',
        'project-requests',
        'project-runs',
        'execution-config',
      ])
        cache.removeQueries({ queryKey: [key, project.id] })
    },
  })
  useEffect(() => {
    const current = dialog.current
    const previous = document.activeElement as HTMLElement | null
    current?.showModal()
    return () => {
      current?.close()
      previous?.focus()
    }
  }, [])
  return (
    <dialog
      ref={dialog}
      className="execution-dialog"
      aria-labelledby="delete-project-title"
      onCancel={(event) => {
        event.preventDefault()
        if (!remove.isPending) onClose()
      }}
    >
      <div className="section-title">
        <div>
          <h2 id="delete-project-title">Excluir projeto?</h2>
          <p>Revise o que será removido da interface antes de confirmar.</p>
        </div>
      </div>
      <div className="request-form">
        <p className="preserve">
          <strong>{project.name}</strong> e suas solicitações deixarão de
          aparecer no cadastro de projetos. O histórico de execuções e a
          auditoria serão preservados.
        </p>
        <div className="info-note">
          Os arquivos do repositório, as branches e as worktrees não serão
          apagados. Esta ação não interrompe agentes.
        </div>
        <p className="mono delete-repo-path">{project.repo_path}</p>
        {busy && (
          <p role="alert" className="form-error">
            Este projeto possui uma execução na fila, em andamento ou com
            processo órfão pendente. Aguarde a conclusão ou a reconciliação
            antes de excluir.
          </p>
        )}
        <label className="form-field">
          Digite o nome do projeto para confirmar
          <input
            value={name}
            autoComplete="off"
            spellCheck={false}
            onChange={(event) => setName(event.target.value)}
            disabled={remove.isPending || busy}
          />
        </label>
        {remove.error && (
          <p role="alert" className="form-error">
            {remove.error.message}
          </p>
        )}
        <div className="form-actions">
          <Button onClick={onClose} disabled={remove.isPending}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={busy || name !== project.name || remove.isPending}
            onClick={() => remove.mutate()}
          >
            <Trash2 size={14} />
            {remove.isPending ? 'Excluindo…' : 'Confirmar exclusão'}
          </Button>
        </div>
      </div>
    </dialog>
  )
}
