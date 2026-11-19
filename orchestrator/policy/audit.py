"""Allowlisted metadata for security-sensitive platform audit actions.

This validates records; it never grants approval, overrides budgets or resumes
a run. Those domain changes must log using their own transaction in future work.
"""
import re


class AuditError(ValueError):
    pass


_FIELDS = {
    'workflow.created': ({'workflow_id'}, set()),
    'workflow.version_created': ({'workflow_id','version_id'}, set()),
    'provider.configured': ({'provider_config_id','adapter'}, {'enabled'}),
    'credential.set': ({'provider_config_id','adapter'}, {'credential_ref'}),
    'credential.removed': ({'provider_config_id','adapter'}, set()),
    'approval.decided': ({'approval_id','decision'}, {'kind','actor_id'}),
    'budget.override': ({'budget_id','approval_id'}, {'run_id','actor_id'}),
    'run.resumed': ({'run_id','approval_id'}, {'checkpoint_id','actor_id'}),
}
_NAMESPACES = {'workflow','provider','credential','approval','budget','run'}
_IDENTIFIER = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}$')


def validate_audit(action, details):
    if not isinstance(action,str): raise AuditError('Unsupported audit action')
    if action not in _FIELDS:
        if action.split('.')[0] in _NAMESPACES:
            raise AuditError('Unsupported audit action')
        return details  # Existing project/request/execution records are unchanged.
    required,optional = _FIELDS[action]
    if not required <= set(details) or set(details) - required - optional:
        raise AuditError('Invalid audit metadata')
    for key,value in details.items():
        if key=='enabled': valid=type(value) is bool
        elif key=='decision': valid=value in ('approve','reject')
        elif key=='kind': valid=value in ('plan','result','resume','budget')
        elif key=='adapter': valid=isinstance(value,str) and re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',value)
        elif key=='credential_ref':
            from ..secrets.store import parse_credential_ref,format_credential_ref
            try:
                service,_=parse_credential_ref(value)
                valid=value==format_credential_ref(details['adapter'],details['provider_config_id'],service=service)
            except Exception:
                valid=False
        elif key=='run_id': valid=isinstance(value,str) and re.fullmatch(r'run-[0-9a-f]{12}',value)
        else: valid=isinstance(value,str) and _IDENTIFIER.fullmatch(value)
        if not valid: raise AuditError('Invalid audit metadata')
    return dict(details)
