from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/webhook/click")
async def click_webhook(request: Request):
    data = await request.json()
    print("Click webhook:", data)
    return {"status": "received"}

@router.post("/webhook/payme")
async def payme_webhook(request: Request):
    data = await request.json()
    print("Payme webhook:", data)
    return {"status": "received"}
