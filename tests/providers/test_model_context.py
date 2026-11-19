import pytest
from orchestrator.providers.context import review_context


def test_context_includes_untracked_text_with_unusual_filenames(tmp_path):
    name = 'new\nfile.txt'
    (tmp_path/name).write_text('bounded text')
    def run(argv,cwd,timeout):
        if '--numstat' in argv: return '1\t0\ttracked.txt'
        return '?? '+name+'\0' if argv[1]=='status' else 'tracked diff'
    items = review_context(str(tmp_path),runner=run,timeout=lambda:10)
    assert items[-1].text=='bounded text'
    assert all(not hasattr(item,'cwd') for item in items)


@pytest.mark.parametrize('kind',['symlink','directory_symlink','hardlink','large','binary','traversal'])
def test_context_fails_closed_on_unsupported_or_escaping_evidence(tmp_path,kind):
    root=tmp_path/'worktree';root.mkdir()
    secret=tmp_path/'private';secret.write_text('outside-secret')
    relative='new.txt'
    if kind=='symlink':(root/relative).symlink_to(secret)
    elif kind=='hardlink':
        import os
        os.link(secret,root/relative)
    elif kind=='directory_symlink':
        (root/'link').symlink_to(tmp_path,target_is_directory=True);relative='link/private'
    elif kind=='large':(root/relative).write_text('x'*32001)
    elif kind=='binary':(root/relative).write_bytes(b'\0')
    else: relative='../private'
    with pytest.raises((OSError,ValueError)):
        review_context(str(root),runner=lambda argv,cwd,t:'?? '+relative+'\0' if argv[1]=='status' else '',timeout=lambda:10)


def test_tracked_binary_changes_are_rejected_before_generation(tmp_path):
    with pytest.raises(ValueError,match='Binary'):
        review_context(str(tmp_path),runner=lambda argv,cwd,t:'-\t-\timage.png' if '--numstat' in argv else '',timeout=lambda:10)
