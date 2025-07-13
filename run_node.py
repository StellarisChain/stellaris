#!/usr/bin/env python3
import uvicorn
import os
import dotenv
from stellaris.node.main import app

dotenv.load_dotenv()

if __name__ == "__main__":
    uvicorn.run("stellaris.node.main:app", host="0.0.0.0", port=int(os.getenv("NODE_PORT", 3006)), reload=False)