import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.api.routes import router as energy_router
from app.api.maintenance_routes import router as maintenance_router
from app.api.occupancy_routes import router as occupancy_router
from app.api.security_routes import router as security_router
from app.api.cost_routes import router as cost_router
from app.api.facility_routes import router as facility_router
from app.api.system_routes import router as system_router
from app.api.auth_routes import router as auth_router
from app.api.anomaly_routes import router as anomaly_router
from app.services import data_service, maintenance_service, occupancy_service, security_service, cost_service
from app.core.security import hash_password
from app.models.auth_models import User

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        # Seed the single demo admin user on first boot only — if ANY user
        # already exists (including one with a different username someone
        # created by hand), this is skipped, so it never clobbers a
        # password someone has since changed.
        if db.query(User).count() == 0:
            db.add(User(username=settings.ADMIN_USERNAME, password_hash=hash_password(settings.ADMIN_PASSWORD), role="admin"))
            db.commit()
            logger.warning(
                f"Seeded default admin user '{settings.ADMIN_USERNAME}' with the password from "
                f"ADMIN_PASSWORD in .env. Change ADMIN_PASSWORD (and JWT_SECRET_KEY) before this "
                f"is anything other than a local demo."
            )
    finally:
        db.close()

    # Auto-ingest on first boot so the dashboard has data immediately in dev.
    db = SessionLocal()
    try:
        if not data_service.has_data(db, "BLD-HQ-01"):
            data_service.ingest_from_csv(db)
        if not maintenance_service.has_data(db, "BLD-HQ-01"):
            try:
                maintenance_service.ingest_fleet(db)
            except FileNotFoundError:
                pass  # dataset not built yet; POST /api/maintenance/ingest once it is
        if not occupancy_service.has_data(db, "BLD-HQ-01"):
            try:
                occupancy_service.ingest_zones(db)
            except FileNotFoundError:
                pass  # dataset not built yet; POST /api/occupancy/ingest once it is
        if not security_service.has_data(db, "BLD-HQ-01"):
            try:
                security_service.ingest_events(db)
            except FileNotFoundError:
                pass  # dataset not built yet; POST /api/security/ingest once it is
        if not cost_service.has_data(db, "BLD-HQ-01"):
            try:
                cost_service.ingest_records(db)
            except FileNotFoundError:
                pass  # dataset not built yet; POST /api/cost/ingest once it is
    finally:
        db.close()
    yield


app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)


# This MUST be registered before CORSMiddleware is added below. Starlette's
# middleware stack wraps outer-to-inner in add-order-reversed, and
# CORSMiddleware only adds its headers to responses that flow back UP
# through it — an exception that escapes past it entirely (e.g. from
# @app.exception_handler(Exception), which sits on the ServerErrorMiddleware
# layer OUTSIDE CORSMiddleware) never gets CORS headers attached, and the
# browser reports it as a generic, misleading "Network Error" even though
# the backend process is alive and every other request is working. Catching
# the exception here — INSIDE CORSMiddleware — turns it into a normal
# Response that CORSMiddleware still gets to process normally, for ANY
# endpoint, not just the AI-provider ones.
@app.middleware("http")
async def catch_unhandled_exceptions(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.exception(f"Unhandled error on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": f"{type(exc).__name__}: {exc}", "path": str(request.url.path)},
        )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(energy_router, prefix=settings.API_V1_PREFIX)
app.include_router(maintenance_router, prefix=settings.API_V1_PREFIX)
app.include_router(occupancy_router, prefix=settings.API_V1_PREFIX)
app.include_router(security_router, prefix=settings.API_V1_PREFIX)
app.include_router(cost_router, prefix=settings.API_V1_PREFIX)
app.include_router(facility_router, prefix=settings.API_V1_PREFIX)
app.include_router(system_router, prefix=settings.API_V1_PREFIX)
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(anomaly_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
def root():
    return {"service": settings.PROJECT_NAME, "status": "running", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy"}
