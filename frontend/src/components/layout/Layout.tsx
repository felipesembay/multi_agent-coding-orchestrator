import {
  Activity,
  Bot,
  ChevronRight,
  CircleHelp,
  Command,
  GitBranch,
  FolderGit2,
  LayoutDashboard,
  ListChecks,
  Menu,
  Radio,
  Settings2,
  ShieldCheck,
  X,
} from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { request } from '../../lib/api'
import { Button } from '../ui/button'
const links = [
  { to: '/', label: 'Projetos', icon: FolderGit2 },
  { to: '/overview', label: 'Overview', icon: LayoutDashboard },
  { to: '/executions', label: 'Executions', icon: ListChecks },
  { to: '/agents', label: 'Agent Monitor', icon: Bot },
  { to: '/reviews', label: 'Tests & Reviews', icon: ShieldCheck },
  { to: '/settings', label: 'Settings', icon: Settings2 },
]
export type DashboardContext = { interval: number }
export function Layout() {
  const [mobile, setMobile] = useState(false)
  const [interval, setInterval] = useState(() => {
    const value = Number(localStorage.getItem('orch-polling') ?? 5000)
    return [0, 5000, 10000, 30000].includes(value) ? value : 5000
  })
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => request<{ status: string }>('/health', signal),
    refetchInterval: interval || false,
  })
  const location = useLocation()
  const page =
    location.pathname === '/projects/new'
      ? 'Novo projeto'
      : location.pathname.startsWith('/projects/')
        ? 'Workspace do projeto'
        : location.pathname === '/projects'
          ? 'Projetos'
          : location.pathname.startsWith('/executions/')
            ? 'Execution Details'
            : (links.find((l) => l.to === location.pathname)?.label ??
              'Página não encontrada')
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        Ir para o conteúdo
      </a>
      <aside
        id="main-navigation"
        className={`sidebar ${mobile ? 'sidebar-open' : ''}`}
      >
        <LinkBrand />
        <div className="workspace">
          <span className="workspace-icon">
            <GitBranch size={17} />
          </span>
          <div>
            <strong>Local workspace</strong>
            <small>Multi-Agent Orchestrator</small>
          </div>
          <span className="local-dot" />
        </div>
        <div className="nav-caption">WORKSPACE</div>
        <nav aria-label="Navegação principal">
          {links.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setMobile(false)}
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="readonly-note">
            <ShieldCheck size={18} />
            <div>
              <strong>Workspace local</strong>
              <p>
                Projetos e solicitações persistentes. Execuções reais pelo
                worker local.
              </p>
            </div>
          </div>
          <div className="sidebar-footer">
            <Command size={14} />
            <span>LangGraph workflow</span>
            <span className="local-dot" />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <Button
              className="mobile-toggle"
              size="icon"
              onClick={() => setMobile(!mobile)}
              aria-expanded={mobile}
              aria-controls="main-navigation"
              aria-label={mobile ? 'Fechar navegação' : 'Abrir navegação'}
            >
              {mobile ? <X size={18} /> : <Menu size={18} />}
            </Button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{page}</strong>
          </div>
          <div className="topbar-right">
            <span
              className={`connection ${health.isError ? 'offline' : ''}`}
              role="status"
            >
              <span />
              {health.isError
                ? 'API desconectada'
                : health.isPending
                  ? 'Conectando…'
                  : 'API conectada'}
            </span>
            <span className="topbar-divider" />
            <label className="polling">
              <Radio size={14} />
              <span className="sr-only">Intervalo de atualização</span>
              <select
                aria-label="Intervalo de atualização"
                value={interval}
                onChange={(e) => {
                  const n = Number(e.target.value)
                  setInterval(n)
                  localStorage.setItem('orch-polling', String(n))
                }}
              >
                <option value={5000}>A cada 5s</option>
                <option value={10000}>A cada 10s</option>
                <option value={30000}>A cada 30s</option>
                <option value={0}>Manual</option>
              </select>
            </label>
          </div>
        </header>
        <main id="main" className="page" tabIndex={-1}>
          <Outlet context={{ interval } satisfies DashboardContext} />
        </main>
        <footer className="page-footer">
          <span>
            <Activity size={13} /> Dados reais · SQLite event store
          </span>
          <span>
            <CircleHelp size={13} /> Horários no fuso do navegador
          </span>
        </footer>
      </div>
    </div>
  )
}
function LinkBrand() {
  return (
    <div className="brand">
      <div className="brand-mark">
        <Command size={22} />
      </div>
      <div>
        <strong>
          orchestrator<span>.</span>
        </strong>
        <small>AGENT CONTROL CENTER</small>
      </div>
    </div>
  )
}
