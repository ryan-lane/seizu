from fastapi import APIRouter

router = APIRouter()


@router.get("/healthcheck", include_in_schema=False)
async def healthcheck() -> dict:
    return {"success": True}
