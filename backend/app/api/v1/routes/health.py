from fastapi import APIRouter

router = APIRouter()


@router.get("/", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
