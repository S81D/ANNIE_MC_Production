"""mcprod: submission-side tools for the ANNIE MC production chain (GENIE -> anniedirt -> WCSim -> toolchain)."""
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STAGES = ("genie", "anniedirt", "wcsim", "toolchain")
