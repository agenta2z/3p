"""Module entrypoint: enables ``python -m openteam.server.resources.tools.project_onboarding``."""
from .cli import main
import sys
sys.exit(main())
