from fastapi import APIRouter

router = APIRouter()


@router.get("/timeline/{patient_id}")
def get_timeline(patient_id: str):
    return {
        "patient_id": patient_id,
        "timeline": [
            {
                "date": "2025-02-01",
                "marker": "LDL",
                "value": 142,
                "unit": "mg/dL"
            },
            {
                "date": "2025-03-01",
                "marker": "LDL",
                "value": 150,
                "unit": "mg/dL"
            }
        ]
    }
