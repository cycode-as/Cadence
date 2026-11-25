# CADENCE Frontend

Server-rendered FastAPI + Jinja2 + HTMX + Tailwind CSS + DaisyUI frontend for **CADENCE** (Army Wing NCC Unit Management Platform).

## Running the Standalone Dev Server

Run from the repository root (`c:\CADENCE`):

```bash
uvicorn frontend.dev_server:app --reload --port 8001
```

Then open `http://127.0.0.1:8001` in your browser.

### Dev Features
- **Role Switcher**: Append `?role=CADET|CADET_LEADER|JUO|ANO|CO|GUEST` to any URL or use the top Dev Toolbar to switch roles (stored in a `dev_role` cookie).
- **Fake WebSocket Event Panel**: Click any event button in the bottom-right Dev Panel (or `POST /dev/emit`) to emit mock WebSocket events over `/ws`, triggering live toast notifications and `#bell` updates.

## Tech Stack
- Python 3.12+ / FastAPI / Jinja2 (sync HTTP routes, no Node.js / npm / build step)
- HTMX `2.0.4` + `htmx-ext-ws@2.0.4`
- Tailwind CSS `3.4.17` (Play CDN) + DaisyUI `4.12.24`
- Chart.js `4.4.4` + SortableJS `1.15.6`

## Folder Structure
- `dev_server.py` — Standalone mock server on port 8001
- `pages/` — Thin FastAPI page/analytics routers
- `templates/` — Jinja2 layouts, components, pages, and HTMX partials
- `static/` — CSS (`app.css`) and vanilla JS (`toast.js`, `ws.js`, etc.)
- `fixtures/mock_context/` — JSON fixtures matching each template's contract
