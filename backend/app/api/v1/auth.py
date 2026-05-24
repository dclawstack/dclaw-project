import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import AuthContext, require_workspace
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember, WorkspaceRole
from app.repositories.user_repo import UserRepository
from app.repositories.workspace_repo import (
    WorkspaceMemberRepository,
    WorkspaceRepository,
)
from app.schemas.auth import (
    AuthMe,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
    WorkspaceCreate,
    WorkspaceMembershipRead,
    WorkspaceRead,
)

router = APIRouter()


_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _slugify(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-") or "workspace"


async def _unique_slug(repo: WorkspaceRepository, base: str) -> str:
    # If the caller's slugified input was empty, use a sensible fallback
    # in BOTH the initial candidate and the dedup loop — otherwise the
    # dedup branch produces degenerate slugs like "-1".
    root = base[:60] or "workspace"
    candidate = root
    counter = 1
    while await repo.get_by_slug(candidate):
        suffix = f"-{counter}"
        candidate = f"{root[: 60 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def _issue_token(user: User, workspace: Workspace) -> TokenResponse:
    token = create_access_token(
        subject=str(user.id), extra_claims={"ws": str(workspace.id)}
    )
    return TokenResponse(
        access_token=token,
        user=UserRead.model_validate(user),
        workspace=WorkspaceRead.model_validate(workspace),
    )


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user and create their first workspace",
)
async def register(body: UserRegister, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    ws_repo = WorkspaceRepository(db)

    if await user_repo.get_by_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    user = User(
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()

    ws_name = body.workspace_name or f"{body.full_name or body.email}'s workspace"
    slug = await _unique_slug(ws_repo, _slugify(ws_name))
    workspace = Workspace(name=ws_name, slug=slug)
    db.add(workspace)
    await db.flush()

    db.add(
        WorkspaceMember(
            workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.owner
        )
    )
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent registration may have grabbed the email or slug
        # between our check and our commit. Return the same 409 the
        # pre-check path would have produced — never leak the SQL error.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or workspace slug already exists — try again",
        )
    await db.refresh(user)
    await db.refresh(workspace)
    return _issue_token(user, workspace)


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, db: AsyncSession = Depends(get_db)):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_email(body.email)
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled"
        )

    workspaces = await WorkspaceRepository(db).list_for_user(user.id)
    if not workspaces:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User has no workspace — create one via /api/v1/workspaces",
        )
    return _issue_token(user, workspaces[0])


@router.get("/me", response_model=AuthMe)
async def me(
    ctx: AuthContext = Depends(require_workspace), db: AsyncSession = Depends(get_db)
):
    workspaces = await WorkspaceRepository(db).list_for_user(ctx.user.id)
    memberships = []
    member_repo = WorkspaceMemberRepository(db)
    for ws in workspaces:
        member = await member_repo.get_membership(ws.id, ctx.user.id)
        memberships.append(
            WorkspaceMembershipRead(
                workspace=WorkspaceRead.model_validate(ws),
                role=member.role.value if member else "viewer",
            )
        )
    return AuthMe(
        user=UserRead.model_validate(ctx.user),
        workspaces=memberships,
        active_workspace=WorkspaceRead.model_validate(ctx.workspace),
    )


@router.post(
    "/switch-workspace/{workspace_id}",
    response_model=TokenResponse,
    summary="Re-issue a token for a different workspace the caller belongs to",
)
async def switch_workspace(
    workspace_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Mint a new token for the target workspace.

    We deliberately do NOT depend on `require_workspace` here: a user
    who was removed from the workspace currently encoded in their JWT
    would otherwise be locked out of switching to a workspace they
    DO still belong to. Instead, we accept any valid token (signature
    + user check) and authorize on the TARGET workspace.
    """
    from app.core.security import decode_token

    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(header.split(" ", 1)[1].strip())
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = UUID(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Token missing claims")
    user = await UserRepository(db).get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unknown user")

    member = await WorkspaceMemberRepository(db).get_membership(workspace_id, user_id)
    if not member:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of that workspace",
        )
    workspace = await WorkspaceRepository(db).get_by_id(workspace_id)
    if not workspace:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    return _issue_token(user, workspace)


workspaces_router = APIRouter()


@workspaces_router.post(
    "/", response_model=WorkspaceRead, status_code=status.HTTP_201_CREATED
)
async def create_workspace(
    body: WorkspaceCreate,
    ctx: AuthContext = Depends(require_workspace),
    db: AsyncSession = Depends(get_db),
):
    ws_repo = WorkspaceRepository(db)
    slug = await _unique_slug(ws_repo, _slugify(body.name))
    workspace = Workspace(name=body.name, slug=slug)
    db.add(workspace)
    await db.flush()
    db.add(
        WorkspaceMember(
            workspace_id=workspace.id, user_id=ctx.user.id, role=WorkspaceRole.owner
        )
    )
    await db.commit()
    await db.refresh(workspace)
    return workspace


@workspaces_router.get("/", response_model=list[WorkspaceRead])
async def list_my_workspaces(
    ctx: AuthContext = Depends(require_workspace),
    db: AsyncSession = Depends(get_db),
):
    return await WorkspaceRepository(db).list_for_user(ctx.user.id)
