"""python -m networth.app: the container entry point, serving on 0.0.0.0:$PORT (Maritime).

uvicorn's access log is off: it writes each request path, and a /u/<token> path is a 30-day
credential to that user's page.
"""

from __future__ import annotations

import logging
import os

import uvicorn

DEFAULT_PORT = 8080

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    port = int(os.environ.get("PORT") or DEFAULT_PORT)
    uvicorn.run("networth.app.main:app", host="0.0.0.0", port=port, proxy_headers=True,
                access_log=False)  # fmt: skip
