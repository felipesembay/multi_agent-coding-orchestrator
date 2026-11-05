
import argparse
import json
import os
from pathlib import Path

from .core import db, execute, resume


def main():
    parser = argparse.ArgumentParser(
        description='Local multi-agent orchestrator'
    )

    sub = parser.add_subparsers(
        dest='command',
        required=True
    )

    run_parser = sub.add_parser('run')
    run_parser.add_argument('--repo', required=True)
    run_parser.add_argument('--scope', required=True)

    resume_parser = sub.add_parser('resume')
    resume_parser.add_argument('--run-id', required=True)

    events_parser = sub.add_parser('events')
    events_parser.add_argument('--run-id')

    args = parser.parse_args()

    if args.command == 'run':
        result = execute(args.repo, args.scope)

    elif args.command == 'resume':
        result = resume(args.run_id)

    else:
        db_path = os.environ.get(
            'ORCH_DB',
            str(
                Path.home()
                / '.local/state/multi-agent-orchestrator/events.db'
            )
        )

        with db(db_path) as conn:
            query = (
                'SELECT run_id, at, stage, payload '
                'FROM events'
            )
            params = []

            if args.run_id:
                query += ' WHERE run_id=?'
                params = [args.run_id]

            query += ' ORDER BY id DESC LIMIT 100'

            for row in conn.execute(query, params):
                print(json.dumps(
                    dict(zip(
                        ('run_id', 'at', 'stage', 'payload'),
                        row
                    )),
                    ensure_ascii=False
                ))

        return

    print(json.dumps(
        {
            key: result.get(key)
            for key in (
                'run_id',
                'status',
                'worktree',
                'task_index',
                'review'
            )
        },
        indent=2,
        ensure_ascii=False
    ))

    if result.get('status') != 'ready_for_human_review':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
