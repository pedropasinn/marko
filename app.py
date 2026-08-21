from __future__ import annotations

import os
from typing import cast

from marko.read_api.app import ApiMode, create_app

mode = cast(ApiMode, os.environ.get("MARKO_API_MODE", "demo"))
app = create_app(mode=mode)
