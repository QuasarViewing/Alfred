from fastapi import FastAPI
import logging

logging.basicConfig(
    filename="alfred.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
#  // Next.js — you know this
#   export async function GET() {
#     return Response.json({ message: "Alfred online" })
#   }

# FastApi Python Syntax
app = FastAPI()


@app.get("/")
def root():
    logging.info("Alfred recieved a request")
    return {"message": "Alfred online"}
