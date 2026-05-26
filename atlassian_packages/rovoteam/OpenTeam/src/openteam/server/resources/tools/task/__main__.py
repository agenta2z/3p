"""Module entrypoint: enables ``python -m openteam.server.resources.tools.task``."""
from .cli import main
import sys
sys.exit(main())
