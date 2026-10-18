import sys

from dragshift.cli import is_cli
from dragshift.handoff import try_handoff

if is_cli(sys.argv):
    from dragshift.cli import main as cli_main
    sys.exit(cli_main())

if try_handoff(sys.argv):
    sys.exit(0)

from dragshift.app import main  # noqa: E402

sys.exit(main())
