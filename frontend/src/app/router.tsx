import { createBrowserRouter, Link } from 'react-router-dom'
import { Layout } from '../components/layout/Layout'
import { OverviewPage } from '../features/Overview'
import { ExecutionsPage } from '../features/Executions'
import { DetailsPage } from '../features/Details'
import { MonitorPage } from '../features/Monitor'
import { SettingsPage } from '../features/Settings'
import { ProjectsPage, NewProjectPage } from '../features/Projects'
import { ProjectWorkspacePage } from '../features/ProjectWorkspace'
export const routes = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <ProjectsPage /> },
      { path: '/projects', element: <ProjectsPage /> },
      { path: '/projects/new', element: <NewProjectPage /> },
      { path: '/projects/:projectId', element: <ProjectWorkspacePage /> },
      { path: '/overview', element: <OverviewPage /> },
      { path: '/executions', element: <ExecutionsPage /> },
      { path: '/executions/:runId', element: <DetailsPage /> },
      { path: '/agents', element: <MonitorPage /> },
      { path: '/reviews', element: <MonitorPage reviews /> },
      { path: '/settings', element: <SettingsPage /> },
      {
        path: '*',
        element: (
          <div className="empty">
            <h1>Página não encontrada</h1>
            <Link to="/">Voltar aos projetos</Link>
          </div>
        ),
      },
    ],
  },
]
export const router = createBrowserRouter(routes)
