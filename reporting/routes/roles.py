"""Routes for user-defined roles."""
import logging
from typing import Any

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from reporting.authnz import CurrentUser
from reporting.authnz import require_permission
from reporting.authnz.permissions import BUILTIN_ROLES
from reporting.authnz.permissions import Permission
from reporting.schema.rbac import CreateRoleRequest
from reporting.schema.rbac import RoleIdResponse
from reporting.schema.rbac import RoleItem
from reporting.schema.rbac import RoleListResponse
from reporting.schema.rbac import RoleVersion
from reporting.schema.rbac import RoleVersionListResponse
from reporting.schema.rbac import UpdateRoleRequest
from reporting.services import report_store

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Built-in role definitions (read-only)
# ---------------------------------------------------------------------------


@router.get("/api/v1/roles/builtin", response_model=RoleListResponse)
async def list_builtin_roles(
    current: CurrentUser = Depends(require_permission(Permission.ROLES_READ)),
) -> RoleListResponse:
    """Return the built-in role definitions (seizu-viewer, seizu-editor, seizu-admin)."""
    roles = [
        RoleItem(
            role_id=f"builtin:{name.replace(' ', '_').lower()}",
            name=name,
            description=f"Built-in role: {name}.",
            permissions=sorted(p.value for p in perms),
            current_version=0,
            created_at="",
            updated_at="",
            created_by="system",
        )
        for name, perms in BUILTIN_ROLES.items()
    ]
    return RoleListResponse(roles=roles)


# ---------------------------------------------------------------------------
# User-defined roles
# ---------------------------------------------------------------------------


@router.get("/api/v1/roles", response_model=RoleListResponse)
async def list_roles(
    current: CurrentUser = Depends(require_permission(Permission.ROLES_READ)),
) -> RoleListResponse:
    """List all user-defined roles."""
    return RoleListResponse(roles=await report_store.list_roles())


@router.post("/api/v1/roles", response_model=RoleItem, status_code=201)
async def create_role(
    body: CreateRoleRequest,
    current: CurrentUser = Depends(require_permission(Permission.ROLES_WRITE)),
) -> Any:
    """Create a new user-defined role."""
    return await report_store.create_role(
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        created_by=current.user.user_id,
    )


@router.get("/api/v1/roles/{role_id}", response_model=RoleItem)
async def get_role(
    role_id: str,
    current: CurrentUser = Depends(require_permission(Permission.ROLES_READ)),
) -> RoleItem:
    """Return a user-defined role by ID."""
    role = await report_store.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.put("/api/v1/roles/{role_id}", response_model=RoleItem)
async def update_role(
    role_id: str,
    body: UpdateRoleRequest,
    current: CurrentUser = Depends(require_permission(Permission.ROLES_WRITE)),
) -> Any:
    """Update a user-defined role (creates a new version)."""
    role = await report_store.update_role(
        role_id=role_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        updated_by=current.user.user_id,
        comment=body.comment,
    )
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.delete("/api/v1/roles/{role_id}", response_model=RoleIdResponse)
async def delete_role(
    role_id: str,
    current: CurrentUser = Depends(require_permission(Permission.ROLES_DELETE)),
) -> RoleIdResponse:
    """Delete a user-defined role and all its versions."""
    ok = await report_store.delete_role(role_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Role not found")
    return RoleIdResponse(role_id=role_id)


@router.get("/api/v1/roles/{role_id}/versions", response_model=RoleVersionListResponse)
async def list_role_versions(
    role_id: str,
    current: CurrentUser = Depends(require_permission(Permission.ROLES_READ)),
) -> RoleVersionListResponse:
    """List all versions of a user-defined role."""
    role = await report_store.get_role(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    versions = await report_store.list_role_versions(role_id)
    return RoleVersionListResponse(versions=versions)


@router.get(
    "/api/v1/roles/{role_id}/versions/{version}",
    response_model=RoleVersion,
)
async def get_role_version(
    role_id: str,
    version: int,
    current: CurrentUser = Depends(require_permission(Permission.ROLES_READ)),
) -> RoleVersion:
    """Return a specific version of a user-defined role."""
    v = await report_store.get_role_version(role_id, version)
    if not v:
        raise HTTPException(status_code=404, detail="Role version not found")
    return v
