#!/usr/bin/env python3
import uvicorn
from stellaris.node.main import app

if __name__ == "__main__":
    uvicorn.run("stellaris.node.main:app", host="0.0.0.0", port=5432, reload=True)