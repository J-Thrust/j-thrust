from fastapi import APIRouter

router = APIRouter()


@router.get("/report/{patient_id}")
def get_report(patient_id: str):
    return {
        "patient_id": patient_id,
        "summary": "Placeholder patient report",
        "risk_score": None,
        "trends": [],
        "recommendations": []
    }
