from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.schemas.guide import GuideRequest, GuideResponse
from app.core.orchestrator import handle

app = FastAPI(title="Setu Guide")


@app.exception_handler(RequestValidationError)
async def bad_input(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"error": {
        "code": "invalid_request", "message": "Request did not match the schema.",
        "details": [str(e["msg"]) for e in exc.errors()]}})


@app.post("/v1/guide/chat", response_model=GuideResponse)
def chat(req: GuideRequest):
    return handle(req)
