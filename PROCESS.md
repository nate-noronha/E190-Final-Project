# Project Engineering & Design Process Log

This document records architectural decisions, test verification results, user interview feedback, and multi-agent coordination history for the Hardware & Machining Prototyping Assistant.

---

## [Phase 0] Environment Setup & Multi-Agent Harmonization
- **Date**: 2026-11-03
- **Agents Involved**: Antigravity Lead Orchestrator
- **Actions Taken**:
  - Installed GitHub CLI (`gh` v2.103.3).
  - Cleaned repository state: restored `README.md`, added `.gitignore` and `.env.example`.
  - Harmonized agent rules: created `AGENTS.md` symlink pointing to `CLAUDE.md`.
  - Configured shared `/reflect` command in both harnesses (`.claude/commands/reflect.md` for Claude Code CLI and `.agents/skills/reflect/SKILL.md` for Antigravity).
  - Added comprehensive `IMPLEMENTATION_PLAN.md` tracking multi-agent roles and 6 vertical slices.
  - Verified GitHub remote connection, opened Pull Request #2, and merged into `main`.
- **Decisions**:
  - Kept single source of truth for engineering directives in `CLAUDE.md`, shared across both agent environments.
  - Configured GitHub CLI authentication via secure credentials.
- **Verification**:
  - PR #2 created and merged cleanly into `main` (commit `aa37c54`).
- **Next Steps**:
  - Branch from `main` to kick off **Slice 1** (FastAPI backend + SQLModel + Dockerized Postgres).

---

## [Slice 1] Multidisciplinary HMC Database Schemas, Role Persistence & Railway Docker Stack
- **Date**: 2026-11-03
- **Agents Involved**: 
  - `Claude-Backend` (Anthropic Claude Code CLI in `.worktrees/wt-1a-backend`)
  - `Claude-DevOps` (Anthropic Claude Code CLI in `.worktrees/wt-1b-devops`)
  - `AGY-Auditor` (Google DeepMind Gemini subagent for cross-model compliance audit)
  - `Lead Orchestrator` (Antigravity Coordinator)
- **Actions Taken**:
  - Provisioned local PostgreSQL 16 test database cluster and Python 3.13 venv.
  - `Claude-Backend` implemented:
    - FastAPI app skeleton with lifespan context manager (`app/main.py`).
    - Database engine management with connection pooling, `reset_engine()` restart simulator, and Railway `postgres://` -> `postgresql+psycopg://` URL normalizer (`app/database.py`).
    - Multidisciplinary HMC SQLModel schemas supporting Student & Steward roles, HMC facilities (`machine_shop`, `wood_shop`, `ee_stockroom`, `makerspace`), `ProjectStep` safety sign-off tracking, `InventoryItem`, and `ProjectBOMItem` campus-vs-external sourcing (`app/models/`).
    - `/health` endpoint returning 200 or honest 503 (without leaking credentials) and `/api/users` CRUD + role-switching endpoints (`app/routers/`).
    - Comprehensive 30-test suite verifying relational integrity, transaction rollbacks, cross-session engine resets, and zero LLM calls on startup or GET routes (`tests/backend/test_persistence.py`).
  - `Claude-DevOps` implemented:
    - Railway-optimized non-root `Dockerfile` respecting dynamic `$PORT`.
    - Local `docker-compose.yml` with persistent named Postgres volume (`postgres_data`).
    - `railway.toml` with `/health` deploy healthcheck.
  - Merged worktrees cleanly into `slice-1-backend-db`.
  - Dispatched `AGY-Auditor` subagent for independent adversarial compliance review. Addressed minor findings (broad 503 exception fallback in `/health`, compose port mapping alignment, and pytest config cleanup).
- **Decisions**:
  - Tagged all inventory items and project steps by HMC facility rather than generic metalworking.
  - Embedded safety gate tracking (`requires_steward_signoff`, `safety_approved_by`, `safety_approved_at`) directly in `ProjectStep` schema.
  - Allowed fast role switching (`PATCH /api/users/{id}/role`) to support seamless shop-floor demoing on mobile during steward interviews.
- **Verification**:
  - Independent Adversarial Audit Report: **VERDICT PASS**.
  - All 30 tests passing against live PostgreSQL in 0.65s.
  - Zero hardcoded secrets; full secret hygiene verified.
- **Next Steps**:
  - Open and merge PR #3 for Slice 1.
  - Proceed to **Slice 2: Stark Greek Design System & Mobile-First Semantic Shell**.

---

## [Slice 2] Stark Greek Design System & Mobile-First Semantic Shell
- **Date**: 2026-11-03
- **Agents Involved**:
  - `Frontend Artisan` (Gemini subagent)
  - `Lead Orchestrator` (Antigravity Coordinator)
- **Actions Taken**:
  - Engineered zero-`<div>` semantic HTML5 application shell (`app/templates/index.html`):
    - Strict semantic tag architecture using `<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, `<dialog>`, `<figure>`, `<figcaption>`, `<ul>`, `<li>`, `<form>`, `<fieldset>`, `<legend>`, `<label>`, `<input>`, `<textarea>`, `<button>`, `<table>`, `<thead>`, `<tbody>`, `<tr>`, `<th>`, `<td>`, `<code>`, `<kbd>`, `<time>`, `<span>`, `<strong>`, `<em>`, `<p>`, `<h1>`-`<h6>`.
    - Exactly 0 `<div>` or `</div>` tags verified across the entire markup.
    - Entablature header with brand title ("ARCHITECT & MAKER", Harvey Mudd College E190), connection status pill (`ONLINE • POSTGRES OK`), and accessible Student vs Steward role switcher.
    - Architectural 4-tab primary navigation: "Project Co-Pilot" (Student workflow), "Steward Safety Queue" (Shop floor sign-offs), "Campus Stockroom" (Inventory catalog), and "3D CAD Preview" (Classmate tool integration harness).
    - Sequential manufacturing step reader featuring interlocked steward safety sign-off gates and visual hazard barriers.
    - Bill of Materials (BOM) tabular checklist auditing campus shelf stock vs external procurement.
    - Steward safety queue with real-time facility filtering across Machine Shop, Wood Shop, EE Stockroom, and Makerspace.
    - Native HTML5 `<dialog id="safety-modal">` for steward physical fixture inspections, PPE validation, and sign-off authorization.
  - Implemented Stark Rustic Black-and-White Greek Design System (`app/static/css/style.css`):
    - Pure #000000 and #FFFFFF utilitarian palette with stark high-contrast borders (1px/2px solid black, 3px double entablature frieze rule).
    - Classical serif typography (Cormorant Garamond, Playfair Display, EB Garamond, Georgia) for architectural headers paired with crisp technical monospacing for tolerances, SKUs, and facility badges (`[EE_STOCKROOM]`, `[MACHINE_SHOP]`, `[WOOD_SHOP]`, `[MAKERSPACE]`).
    - Mobile-first responsiveness strictly targeting phone width (320px–390px) with touch targets >= 44px for shop stewards walking around machine shop floors.
  - Developed vanilla client interaction script (`app/static/js/app.js`):
    - Strict enforcement of ZERO LLM calls on page load (DOMContentLoaded only pings `GET /health` to update connection status pill).
    - Accessible tab navigation, dynamic role switcher toggle, interactive subsystem filters, native modal `showModal()` / `close()` handling, and live inventory search/filter.
  - Integrated static file mounting and root route in `app/main.py`:
    - Mounted `/static` directory via `StaticFiles(directory=str(STATIC_DIR), html=True)`.
    - Route `GET /` serves `app/templates/index.html` with Content-Type `text/html`.
  - Authored comprehensive frontend test suite (`tests/frontend/test_semantic_ui.py`):
    - 13 automated tests verifying zero `<div>` tags, all required semantic landmarks, mobile-first `<meta name="viewport">`, HTTP 200 `text/html`, zero LLM calls on page load, static asset reachability, and CSS design system compliance.
- **Verification**:
    - All 13 frontend tests passed.
    - Full test suite (43 tests: 30 backend persistence + 13 frontend semantic UI) passing in 0.82s.
- **Next Steps**:
    - Commit on branch `slice-2-frontend-shell` and submit report.

