"""HTTP contract for the first operational increment: projects and requests."""
from fastapi import APIRouter

from . import projects, execution_manager
from .local_security import CSRF_TOKEN

router = APIRouter()


@router.get('/session')
def session():
    return {'csrf_token': CSRF_TOKEN}


@router.get('/project-policy')
def project_policy():
    return projects.policy()


@router.get('/projects')
def list_projects():
    return projects.list_projects()


@router.post('/projects/preview')
def preview_project(data: projects.ProjectInput):
    return projects.preview(data)


@router.post('/projects', status_code=201)
def create_project(data: projects.ProjectConfirmation):
    return projects.create(data)


@router.get('/projects/{project_id}')
def get_project(project_id: str):
    return projects.get_project(project_id)


@router.patch('/projects/{project_id}')
def update_project(project_id: str, data: projects.ProjectUpdate):
    return projects.update_project(project_id, data)


@router.get('/projects/{project_id}/requests')
def list_requests(project_id: str):
    return projects.requests(project_id)


@router.post('/projects/{project_id}/requests', status_code=201)
def create_request(project_id: str, data: projects.RequestInput):
    return projects.submit_request(project_id, data)


@router.get('/projects/{project_id}/execution-config', response_model=execution_manager.PreflightResponse)
def execution_config(project_id: str):
    return execution_manager.preflight(project_id)


@router.post('/projects/{project_id}/requests/{request_id}/runs', status_code=202,
             response_model=execution_manager.StartResponse)
def start_run(project_id: str, request_id: str, data: execution_manager.StartInput):
    return execution_manager.submit(project_id, request_id, data)


@router.get('/projects/{project_id}/runs')
def repository_runs(project_id: str, linked_only: bool = False):
    return execution_manager.project_runs(project_id, legacy=not linked_only)
