"""Module entrypoint: enables ``python -m openteam.server.resources.tools.role_setup``."""
from .cli import main
import sys
sys.exit(main())
