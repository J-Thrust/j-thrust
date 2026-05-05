from fastapi import FastAPI
from app.routes import upload, analyze, report, timeline, graph

app = FastAPI(title="Patient Analysis Backend")

app.include_router(upload.router, prefix="/api")
app.include_router(analyze.router, prefix="/api")
app.include_router(report.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(graph.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "Backend is running"}
