from fastapi import APIRouter, UploadFile, File

router = APIRouter()


@router.post("/upload")
async def upload_csv(file: UploadFile = File(...)):
    return {
        "status": "success",
        "filename": file.filename,
        "message": "Upload endpoint connected"
    }
