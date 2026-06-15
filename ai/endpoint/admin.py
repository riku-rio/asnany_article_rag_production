from fastapi import APIRouter, HTTPException

from database.admin_service import (
    get_stats,
    list_knowledge,
    get_knowledge,
    delete_knowledge,
    get_logs,
    check_health,
)

router = APIRouter()


@router.get("/stats")
def stats():
    try:
        return get_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge")
def knowledge_list():
    try:
        return list_knowledge()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/knowledge/{id}")
def knowledge_detail(id: int):
    try:
        item = get_knowledge(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not item:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return item


@router.delete("/knowledge/{id}")
def knowledge_delete(id: int):
    try:
        deleted = delete_knowledge(id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if not deleted:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return {"success": True, "message": "Knowledge deleted"}


@router.get("/logs")
def logs(limit: int = 50):
    capped = min(limit, 200)
    try:
        return get_logs(limit=capped)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
def health():
    return check_health()
