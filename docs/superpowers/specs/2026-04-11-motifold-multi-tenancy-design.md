# Motifold Multi-Tenancy Design (Separate Schema)

## Overview

Add Organization (Org) support with **per-org database schemas**. Each organization gets its own PostgreSQL schema containing all business data. Shared reference data lives in `public` schema.

**Model:** Linear-style — single user account, multiple Organizations, personal Workspaces with optional collaboration.

---

## Database Architecture

### Schema Layout

```
public schema (shared reference data):
  ├── users                  # Global user accounts
  ├── organizations          # Org metadata (name, slug, status)
  └── organization_members   # Which user belongs to which org with role

org_{slug} schema (per-organization):
  ├── workspaces
  ├── chats
  ├── messages
  ├── blackboards
  ├── keywords
  ├── morphological_analyses
  └── research_reports
```

### Key Design Decisions

1. **Schema naming:** `org_{slug}` (e.g., `org_acme`, `org_foo_bar`)
2. **Org creation:** Async with status polling. `organizations.status` field: `provisioning` | `active` | `failed`
3. **Schema provisioning:** `CREATE SCHEMA org_{slug}` + Alembic migration per schema
4. **Query routing:** All org-scoped queries use `SET search_path TO org_{slug}, public`
5. **User query across orgs:** Always use `public` schema directly

---

## Data Model

### public.organizations
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | String | Display name |
| slug | String(unique) | URL-friendly, becomes schema name |
| status | String | `provisioning`, `active`, `failed` |
| created_at | DateTime | Creation timestamp |

### public.organization_members
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| organization_id | UUID(FK) | Reference to organizations |
| user_id | UUID(FK) | Reference to users |
| role | String | `owner` / `admin` / `member` |
| joined_at | DateTime | When user joined |

### users (unchanged except UUID PK)
- Change `id` from Integer to UUID

### org_{slug}.workspaces
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID(FK) | Original creator/owner |
| name | String | Workspace name |
| created_at | DateTime | Creation timestamp |

Other tables in org schema follow same pattern: id (UUID), user_id (FK to public.users), resource-specific fields, timestamps.

### Relationships
```
Organization (public)
  └── OrganizationMember (public) → User (public)
          └── Workspace (org_{slug})
                  └── Chat, Blackboard, Matrix, ResearchReport (org_{slug})
```

---

## Tenant Resolution

**Mechanism:** JWT (user_id) + Request Header (X-Org-ID)

Flow:
1. User logs in → receives JWT with `user_id`
2. Frontend stores `current_org_id` in state/localStorage
3. API request → Header `X-Org-ID: <org_slug>` (use slug, not ID)
4. Backend middleware extracts org_slug, validates user is member
5. Set `search_path` to `org_{slug}, public`
6. All queries run in org's schema

**Schema resolution:**
- Org slug → schema name: `org_{slug}`
- Validate slug format: lowercase alphanumeric + underscore only
- Query: `SELECT * FROM organizations WHERE slug = ? AND status = 'active'`

**Validation:**
- If `X-Org-ID` missing → 400 Bad Request
- If user not org member → 403 Forbidden
- If org status ≠ `active` → 503 Service Unavailable (still provisioning/failed)

---

## Org Provisioning Flow (Async)

### Step 1: Create Org (API)
```
POST /api/orgs
  → Creates organizations row with status='provisioning'
  → Returns { id, slug, status: 'provisioning' }
  → Triggers background task
```

### Step 2: Background Provisioning Task
```
1. CREATE SCHEMA org_{slug}
2. Set search_path to new schema
3. Run Alembic migrations (create workspaces, chats, etc. tables)
4. Update organizations.status = 'active'
   OR status = 'failed' with error message
```

### Step 3: Client Polls Status
```
GET /api/orgs/{id}
  → Returns { status: 'provisioning' | 'active' | 'failed' }
Client polls every 1-2 seconds until 'active'
```

---

## Authorization

### Org-Level Roles (in public.organization_members)
| Role | Permissions |
|------|-------------|
| owner | Full control, delete org, manage billing |
| admin | Manage members, create workspaces |
| member | Create workspaces, use resources |

### Workspace-Level Roles (in org_{slug}.workspace_members)
| Role | Permissions |
|------|-------------|
| owner | Full control, delete workspace, manage members |
| member | Create/edit resources |
| viewer | Read-only access |

### Permissions Matrix
| Action | Who Can Do It |
|--------|--------------|
| Create Org | Any authenticated user (becomes owner) |
| Delete Org | Org owner only |
| Invite Org Member | Org owner or admin |
| Remove Org Member | Org owner or admin |
| Create Workspace | Org owner, admin, or member |
| Delete Workspace | Workspace owner only |
| Invite to Workspace | Workspace owner or org admin |
| Manage Org Settings | Org owner or admin |

---

## API Changes

### New Endpoints
- `POST /api/orgs` — Create organization (async, returns immediately)
- `GET /api/orgs` — List user's organizations
- `GET /api/orgs/:id` — Get organization (includes status field)
- `POST /api/orgs/:id/members` — Invite member
- `DELETE /api/orgs/:id/members/:user_id` — Remove member
- `GET /api/orgs/:id/members` — List members
- `POST /api/workspaces/:id/members` — Invite to workspace
- `DELETE /api/workspaces/:id/members/:user_id` — Remove from workspace
- `GET /api/workspaces/:id/members` — List workspace members

### Header Requirement
All org-scoped API endpoints require `X-Org-ID: <slug>` header.
Auth endpoints (`/auth/*`) do NOT require org header.

### Response Format
```json
{
  "data": [...],
  "organization": {
    "id": "uuid",
    "name": "Acme Corp",
    "slug": "acme",
    "status": "active"
  }
}
```

---

## Migration Strategy

### Phase 1: Schema Separation (this implementation)
1. Add UUID support (generate UUIDs for existing Integer PKs)
2. Create `public` schema tables (organizations, organization_members)
3. Modify existing migrations to use `search_path`
4. Add `organization_id` / `org_slug` resolution middleware

### Phase 2: Async Provisioning
1. Add `status` column to organizations
2. Create background task infrastructure
3. Implement schema creation + migration flow

### Phase 3: Backward Compatibility
1. Existing user data → migrate to `public` schema with default org
2. Existing workspace data → migrate to `org_default` schema
3. Phase out Integer PKs in favor of UUIDs

---

## Frontend Changes

### Org Selector
- Top-left dropdown showing current org
- "Personal" option for non-org resources
- Org creation/invite flow
- Status indicator during org provisioning

### Sidebar Layout
```
[Org Selector ▼]
────────────────
 Workspace 1 (personal)
 Workspace 2 (shared)
   └── Chat
   └── Matrix
────────────────
[Settings] [Members]
```

### Protected Routes
- `/org/:orgSlug/*` — requires org membership + active status
- Personal routes without org → use special `personal` org context

---

## Testing

1. **Unit tests** — org/workspace membership checks
2. **Integration tests** — API with X-Org-ID header + schema isolation
3. **E2E tests** — Create org → invite member → share workspace
4. **Schema isolation tests** — Verify org A cannot see org B data

---

## Out of Scope (Phase 1)

- Subdomain-based tenant resolution
- SSO/SAML authentication
- Per-org feature flags
- Org-level billing
- Automatic schema cleanup on org deletion (manual process)

---

## Key Implementation Notes

1. **Schema name escaping:** Always use `org_{slug}` format, validate slug contains only `[a-z0-9_]`
2. **Search path:** Always `SET search_path TO org_{slug}, public` before org-scoped queries
3. **UUID PKs:** Use UUID v4 for all new primary keys; existing Integer PKs preserved until migration
4. **Foreign keys to public:** Org schema tables reference `public.users.id` directly (cross-schema FKs supported by PostgreSQL)
