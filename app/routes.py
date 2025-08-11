from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def home():
    return {"message": "Flower Shop Bot API is running!"}
