from fastapi import APIRouter

router = APIRouter()


@router.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"message": "myhomecircle API"}
