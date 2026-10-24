"""python -m networth.web: the pages alone on 127.0.0.1:8090, for development and review."""

import uvicorn
from fastapi import FastAPI

from networth.web.routes import router

HOST, PORT = "127.0.0.1", 8090

app = FastAPI(title="Networth web")
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
