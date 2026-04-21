"""Built-in ``roles__*`` tools — built-in + user-defined role management."""
from typing import Any
from typing import Dict
from typing import Optional

from reporting.authnz import CurrentUser
from reporting.authnz.permissions import BUILTIN_ROLES
from reporting.authnz.permissions import Permission
from reporting.schema.rbac import CreateRoleRequest
from reporting.schema.rbac import UpdateRoleRequest
from reporting.services import report_store
from reporting.services.mcp_builtins.base import BuiltinGroup
from reporting.services.mcp_builtins.base import BuiltinTool
from reporting.services.mcp_builtins.base import model_input_schema

GROUP = "roles"


def _require_user(current_user: Optional[CurrentUser]) -> CurrentUser:
    if current_user is None:
        raise RuntimeError("No current user on the request context")
    return current_user


def _role_id_prop() -> Dict[str, Any]:
    return {"role_id": {"type": "string"}}


async def _list_builtin(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    return {
        "roles": [
            {
                "role_id": f"builtin:{name.replace(' ', '_').lower()}",  # noqa: E231
                "name": name,
                "description": f"Built-in role: {name}.",
                "permissions": sorted(p.value for p in perms),
            }
            for name, perms in BUILTIN_ROLES.items()
        ]
    }


async def _list(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    roles = await report_store.list_roles()
    return {"roles": [r.model_dump() for r in roles]}


async def _get(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    role = await report_store.get_role(args["role_id"])
    if not role:
        return {"error": "Role not found"}
    return role.model_dump()


async def _create(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    user = _require_user(current_user)
    body = CreateRoleRequest.model_validate(args)
    role = await report_store.create_role(
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        created_by=user.user.user_id,
    )
    return role.model_dump()


async def _update(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    user = _require_user(current_user)
    role_id = args["role_id"]
    body = UpdateRoleRequest.model_validate(
        {k: v for k, v in args.items() if k != "role_id"}
    )
    role = await report_store.update_role(
        role_id=role_id,
        name=body.name,
        description=body.description,
        permissions=body.permissions,
        updated_by=user.user.user_id,
        comment=body.comment,
    )
    if not role:
        return {"error": "Role not found"}
    return role.model_dump()


async def _delete(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    ok = await report_store.delete_role(args["role_id"])
    if not ok:
        return {"error": "Role not found"}
    return {"role_id": args["role_id"]}


async def _list_versions(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    role_id = args["role_id"]
    role = await report_store.get_role(role_id)
    if not role:
        return {"error": "Role not found"}
    versions = await report_store.list_role_versions(role_id)
    return {"versions": [v.model_dump() for v in versions]}


async def _get_version(
    args: Dict[str, Any], current_user: Optional[CurrentUser]
) -> Dict[str, Any]:
    v = await report_store.get_role_version(args["role_id"], int(args["version"]))
    if not v:
        return {"error": "Role version not found"}
    return v.model_dump()


GROUP_DEF = BuiltinGroup(
    name=GROUP,
    tools=[
        BuiltinTool(
            name="roles__list_builtin",
            group=GROUP,
            description="Return the built-in role definitions (seizu-viewer, seizu-editor, seizu-admin).",
            input_schema={"type": "object", "properties": {}},
            required_permissions=[Permission.ROLES_READ.value],
            handler=_list_builtin,
        ),
        BuiltinTool(
            name="roles__list",
            group=GROUP,
            description="List all user-defined roles.",
            input_schema={"type": "object", "properties": {}},
            required_permissions=[Permission.ROLES_READ.value],
            handler=_list,
        ),
        BuiltinTool(
            name="roles__get",
            group=GROUP,
            description="Return a user-defined role by ID.",
            input_schema={
                "type": "object",
                "properties": _role_id_prop(),
                "required": ["role_id"],
            },
            required_permissions=[Permission.ROLES_READ.value],
            handler=_get,
        ),
        BuiltinTool(
            name="roles__create",
            group=GROUP,
            description="Create a new user-defined role.",
            input_schema=model_input_schema(CreateRoleRequest),
            required_permissions=[Permission.ROLES_WRITE.value],
            handler=_create,
            requires_user=True,
        ),
        BuiltinTool(
            name="roles__update",
            group=GROUP,
            description="Update a user-defined role (creates a new version).",
            input_schema=model_input_schema(
                UpdateRoleRequest,
                extra_properties=_role_id_prop(),
                extra_required=["role_id"],
            ),
            required_permissions=[Permission.ROLES_WRITE.value],
            handler=_update,
            requires_user=True,
        ),
        BuiltinTool(
            name="roles__delete",
            group=GROUP,
            description="Delete a user-defined role and all its versions.",
            input_schema={
                "type": "object",
                "properties": _role_id_prop(),
                "required": ["role_id"],
            },
            required_permissions=[Permission.ROLES_DELETE.value],
            handler=_delete,
        ),
        BuiltinTool(
            name="roles__list_versions",
            group=GROUP,
            description="List all versions of a user-defined role.",
            input_schema={
                "type": "object",
                "properties": _role_id_prop(),
                "required": ["role_id"],
            },
            required_permissions=[Permission.ROLES_READ.value],
            handler=_list_versions,
        ),
        BuiltinTool(
            name="roles__get_version",
            group=GROUP,
            description="Return a specific version of a user-defined role.",
            input_schema={
                "type": "object",
                "properties": {
                    **_role_id_prop(),
                    "version": {"type": "integer"},
                },
                "required": ["role_id", "version"],
            },
            required_permissions=[Permission.ROLES_READ.value],
            handler=_get_version,
        ),
    ],
)
