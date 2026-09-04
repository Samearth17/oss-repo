import argparse, os
from django.core.management import execute_from_command_line
from src.dashboard import run_scan
parser = argparse.ArgumentParser(description="OSS Watch Django repository intelligence app")
parser.add_argument("--demo", action="store_true", help="Use bundled offline fixtures")
parser.add_argument("--port", type=int, default=8000)
parser.add_argument("--scan", action="store_true", help="Run a monitoring scan before starting the server")
args, _ = parser.parse_known_args()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "osswatch.settings")
os.environ["OSS_WATCH_MODE"] = "DEMO" if args.demo else "LIVE"
if args.demo or args.scan:
    run_scan()
print(f"OSS Watch Django server running in {os.environ['OSS_WATCH_MODE']} mode at http://127.0.0.1:{args.port}")
execute_from_command_line(["manage.py", "runserver", f"127.0.0.1:{args.port}", "--noreload"])
