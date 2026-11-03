# Project Overview
This project is a hardware and machining prototyping assistant for engineering students. It breaks down complex physical projects into step-by-step instructions, integrates safety check-offs from shop stewards, and tracks makerspace/stockroom inventory.

## Tech Stack
*   **Backend:** FastAPI, Python.
*   **Database:** Postgres with SQLModel ORM. 
*   **Frontend:** Plain HTML, vanilla JavaScript, and CSS. No heavy frontend frameworks (no React, Vue, etc.).
*   **Deployment:** Docker, optimized for Railway.

## Core Directives & Constraints
1.  **Mobile-First Frontend:** All HTML/CSS must be semantic, accessible, and fully functional at phone width. Never use generic `<div>` soup; use `<main>`, `<article>`, `<section>`, etc.
2.  **LLM Interaction Rules:** 
    *   The LLM must *only* be triggered by explicit user actions (e.g., submitting a project form or sending a chat message). 
    *   **CRITICAL:** Never call the LLM on page load.
    *   Always handle and display honest network failure states to the user if the model call fails.
3.  **Database Persistence & Roles:** 
    *   Database schemas must support at least two user roles: `Student` (submits projects, reads instructions) and `Steward` (approves safety steps, manages inventory).
    *   Ensure all data writing is properly committed so that it survives redeploys.
4.  **Aesthetic:** The UI is a minimal, rustic, black-and-white Greek theme. Use high-contrast layouts, serif fonts for headings, and clean sans-serif/monospace fonts for technical readouts. Keep the design stark and utilitarian.
5.  **Secrets:** Never commit API keys or database credentials to git. Always use environment variables (`os.getenv`).
6.  **Pending Integrations:** 
    *   Leave a placeholder architecture for a third-party API integration (to be determined).
    *   Leave a placeholder for bulk CSV inventory uploads pending steward workflow discussions.

## Workflow Instructions
*   Keep commits small and focused. Generate code one slice at a time.
*   Always wait for my review and explicit approval on Pull Requests.
*   Log design process updates, test results, and user interviews using the `/reflect` skill to update `PROCESS.md`.
