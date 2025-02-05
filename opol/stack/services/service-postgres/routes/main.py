from fastapi import APIRouter
from .search.routes import router as search_router
from .pipelines.routes import router as pipeline_router
from .helper.routes import router as helper_router
from .dimensions.routes import router as dimensions_router
from .v2.search.routes import router as v2_search_router
from .v2.documents.routes import router as v2_documents_router
from .v2.search.contents.routes import router as v2_contents_router
from .v2.search.entities.routes import router as v2_entities_router
from .v2.search.scores.routes import router as v2_scores_router

api_router = APIRouter()

api_router.include_router(search_router, tags=["search"])
api_router.include_router(pipeline_router, tags=["pipelines"])
api_router.include_router(helper_router, tags=["helper"])
api_router.include_router(dimensions_router, tags=["dimensions"])


api_router.include_router(v2_search_router, prefix="/api/v2/search", tags=["v2-search"])
api_router.include_router(v2_contents_router, prefix="/api/v2/search/contents", tags=["v2-contents"])
api_router.include_router(v2_entities_router, prefix="/api/v2/search/entities", tags=["v2-entities"])
api_router.include_router(v2_scores_router, prefix="/api/v2/search/scores", tags=["v2-scores"])
api_router.include_router(v2_documents_router, prefix="/api/v2/documents", tags=["v2-documents"])
