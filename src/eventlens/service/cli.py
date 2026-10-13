"""Operations entry point; independent of the checkout and historical fixtures."""
import argparse
import json
import sys
from pathlib import Path

from ..macro.records import load_sources
from .providers import refresh_calendars, PROVIDERS
from .settings import Settings
from .store import Database


def main(argv=None):
    parser = argparse.ArgumentParser(description='EventLens service operations')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('serve'); p.add_argument('--host', default='127.0.0.1'); p.add_argument('--port', type=int, default=8000)
    sub.add_parser('worker')
    p = sub.add_parser('seed'); p.add_argument('--manifest', type=Path, required=True)
    p = sub.add_parser('refresh'); p.add_argument('--limit', type=int, default=8)
    p.add_argument('--providers', nargs='+', choices=PROVIDERS, default=list(PROVIDERS))
    sub.add_parser('check')
    p = sub.add_parser('request', help='Request a current brief from the running service')
    p.add_argument('--url', default='http://127.0.0.1:8000')
    p.add_argument('--markets', nargs='+', choices=['CN','HK','TW','SEA','EU','US','JP','GLOBAL'], default=['GLOBAL'])
    p.add_argument('--days', type=int, default=14)
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--method', choices=['agent', 'single', 'rules'], default='agent')
    p.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'request':
            from .client import request_brief
            return request_brief(args)
        settings = Settings.from_env()
        db = Database(settings.database)
        if args.command == 'serve':
            import uvicorn
            from .api import create_app
            uvicorn.run(create_app(settings), host=args.host, port=args.port, access_log=False)
        elif args.command == 'worker':
            from .worker import main as worker_main
            worker_main()
        elif args.command == 'seed':
            _, sources = load_sources(args.manifest)
            added = sum(db.add_source(s, {'method': 'manifest-import', 'manifest': args.manifest.name}) for s in sources.values())
            print(json.dumps({'added': added, 'sources': len(sources)}))
        elif args.command == 'refresh':
            result = refresh_calendars(db, args.providers, args.limit)
            print(json.dumps(result, indent=2))
            return 1 if result['errors'] else 0
        elif args.command == 'check':
            health = db.health()
            print(json.dumps(health))
            return 0 if health['workers'] else 1
        return 0
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
