"""Module entrypoint: enables ``python -m openteam.server.resources.tools.create_role``."""
from .cli import main
import sys
sys.exit(main())
