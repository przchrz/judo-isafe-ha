"""Make the integration package importable without a Home Assistant install.

Only the pure-protocol modules are exercised here; they deliberately avoid
Home Assistant imports so the wire format can be tested in isolation.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "judo_isafe"))
