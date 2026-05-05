from fastapi import APIRouter

router = APIRouter()


@router.post("/analyze/{patient_id}")
def analyze_patient(patient_id: str):
    return {
        "patient_id": patient_id,
        "status": "placeholder",
        "message": "Analysis endpoint connected"
    }
