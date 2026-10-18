import sys

from dropdial.cli import is_cli
from dropdial.handoff import try_handoff

if is_cli(sys.argv):
    from dropdial.cli import main as cli_main
    sys.exit(cli_main())

if try_handoff(sys.argv):
    sys.exit(0)

from dropdial.app import main  # noqa: E402

sys.exit(main())
