"""Durable graph checkpoints in a separate database, never an auto-resume API."""
from contextlib import contextmanager
import os
from pathlib import Path
import re
import sqlite3
import stat

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from ..core import db_path


class CheckpointError(RuntimeError):
    pass


def checkpoint_path():
    catalog = Path(db_path()).expanduser().resolve()
    return catalog.with_name(catalog.name + '.checkpoints.sqlite3')


def checkpoint_config(run_id):
    if not isinstance(run_id,str) or not re.fullmatch(r'run-[0-9a-f]{12}',run_id):
        raise CheckpointError('Invalid checkpoint run identity')
    return {'configurable':{'thread_id':run_id}}


@contextmanager
def open_checkpointer():
    path = checkpoint_path()
    conn = None
    try:
        path.parent.mkdir(parents=True,exist_ok=True)
        fd = os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise CheckpointError('Unsupported checkpoint store')
            os.fchmod(fd,0o600)
        finally:
            os.close(fd)
        conn = sqlite3.connect(path,timeout=30,check_same_thread=False)
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA synchronous=FULL')
        serializer = JsonPlusSerializer(pickle_fallback=False,
            allowed_json_modules=[],allowed_msgpack_modules=[])
        saver = SqliteSaver(conn,serde=serializer)
        saver.jsonplus_serde = serializer
        saver.setup()
    except (OSError,sqlite3.Error,CheckpointError):
        if conn is not None: conn.close()
        raise CheckpointError('Cannot open checkpoint store') from None
    try:
        yield saver
    finally:
        conn.close()
