# How This App Works — Explained Like You're 10

Welcome! This guide explains the entire Innovo Claude app from scratch.
No prior knowledge needed. We'll use simple analogies throughout.

---

## Table of Contents

1. [The Big Picture — What Does This App Do?](#1-the-big-picture)
2. [The Restaurant Analogy — Frontend vs Backend](#2-the-restaurant-analogy)
3. [The Database — Our Filing Cabinet](#3-the-database)
4. [How Data Flows — Step by Step](#4-how-data-flows)
5. [The AI Brain — How Documents Get Written](#5-the-ai-brain)
6. [Authentication — Who Are You?](#6-authentication)
7. [The Project Lifecycle — From Zero to Document](#7-the-project-lifecycle)
8. [All the Moving Parts — File by File](#8-all-the-moving-parts)
9. [External Services — Things We Borrow](#9-external-services)
10. [The Full Journey — One Example From Start to Finish](#10-the-full-journey)

---

## 1. The Big Picture

**What does this app do?**

This app helps consultants at Innovo write **funding application documents** automatically.

Imagine a company called "RobotCo" wants to apply for government money to build robots.
They need to write a long, formal document explaining what they do, why they deserve the money,
and how the project fits the rules of a funding program.

Writing this takes **days**. This app uses AI to write a first draft in **minutes**.

Here's the flow at a glance:
```
User tells the app:
  → "I'm helping company X apply for funding program Y, the project is about Z"

The app then:
  1. Looks up everything about company X
  2. Reads the rules of funding program Y
  3. Researches topic Z on the internet
  4. Asks an AI to write the document
  5. Shows the user the draft to review and edit
  6. Exports a final Word/PDF document
```

---

## 2. The Restaurant Analogy

Think of the app like a restaurant.

```
CUSTOMER (You, the user)
   ↓
WAITER (Frontend — React)
   ↓
KITCHEN (Backend — FastAPI)
   ↓
PANTRY (Database — PostgreSQL)
```

### The Waiter (Frontend)
- Lives in the `frontend/` folder
- Built with **React** (a JavaScript framework for building web pages)
- The waiter takes your order (clicks, form inputs) and brings it to the kitchen
- The waiter also brings the finished food (data) back to your table (screen)
- The waiter does NOT cook anything — it just shows things and sends requests

### The Kitchen (Backend)
- Lives in the `backend/` folder
- Built with **FastAPI** (a Python framework for handling web requests)
- The kitchen actually does the work: saves data, talks to the AI, processes files
- The kitchen speaks in **API endpoints** — these are like menu items the waiter can order

### The Pantry (Database)
- Lives in **PostgreSQL** (a database) — like a giant organized filing cabinet
- Stores all users, companies, documents, projects, chat messages, etc.
- The kitchen reads from and writes to the pantry
- Managed with **SQLAlchemy** (Python code that talks to the database)

### The Recipe Book (Schemas & Models)
- `backend/app/models.py` — defines what tables exist in the filing cabinet
- `backend/app/schemas.py` — defines what data looks like when sent over the internet

---

## 3. The Database — Our Filing Cabinet

The database has **drawers** (tables). Each drawer holds one type of record.

Think of each row in a table like one index card in a drawer.

### Main Drawers

| Drawer (Table) | What's Inside |
|----------------|--------------|
| `users` | Everyone who has an account (email, password hash) |
| `companies` | Company profiles (name, website, what they do) |
| `funding_programs` | Available funding programs (name, rules) |
| `documents` | The actual generated documents (sections, text content) |
| `projects` | A project ties together: company + funding program + topic |
| `project_contexts` | Pre-researched info for a project (like a research dossier) |
| `project_chat_messages` | The chat history between user and AI assistant |
| `files` | Uploaded files (PDFs, audio recordings) |
| `user_templates` | Custom document templates per user |

### How Tables Connect

```
users
  └── owns → projects
                ├── links to → companies
                ├── links to → funding_programs
                ├── has one → project_contexts  (the research dossier)
                ├── has many → project_chat_messages
                └── has one → documents
                               └── export → .docx / .pdf file
```

A `project` is the central thing. Everything connects through it.

---

## 4. How Data Flows

### What is an API?

An **API** (Application Programming Interface) is like a menu of actions the backend can do.

Each item on the menu has:
- An **HTTP method** (GET = fetch, POST = create, PUT = update, DELETE = remove)
- A **URL path** (like `/projects` or `/documents/42/generate-content`)

When the frontend wants something, it sends an **HTTP request** to one of these paths.
The backend receives it, does the work, and sends back an **HTTP response**.

### Example: Creating a Project

```
FRONTEND sends:
  POST /projects
  Body: { "company_name": "RobotCo", "funding_program_id": 3, "topic": "Welding robots" }

BACKEND receives it in: backend/app/routers/projects.py
  └── Saves a new row in the "projects" table
  └── Kicks off background research (more on this below)
  └── Sends back: { "id": 7, "status": "assembling", ... }

FRONTEND gets the response:
  └── Shows a loading screen while research is happening
```

### The API Menu (All Endpoints)

**Auth (Who you are):**
- `POST /auth/login` — log in, get a token
- `POST /auth/register` — create an account

**Projects (the main thing):**
- `POST /projects` — create a new project
- `GET /projects` — list all my projects
- `GET /projects/{id}` — get one project
- `POST /projects/{id}/chat` — chat with AI about the project

**Documents (the output):**
- `POST /documents/{id}/generate-content` — ask AI to write the document
- `POST /documents/{id}/chat` — ask AI to edit a section
- `GET /documents/{id}/export` — download as Word or PDF

**Companies:**
- `POST /companies` — add a company
- `POST /companies/{id}/crawl-website` — scrape their website

**Funding Programs:**
- `POST /funding-programs/{id}/upload-guidelines` — upload the PDF rulebook

---

## 5. The AI Brain — How Documents Get Written

The AI is **not** built into the app. We call **OpenAI's API** (GPT-4o-mini).

Think of it like calling a very smart friend on the phone:
- We write them a detailed letter (the **prompt**)
- They write back with the document content
- We save what they wrote into the database

### Who Builds the Letter? (PromptBuilder)

The file `backend/app/services/prompt_builder.py` is like a letter-writing machine.

It assembles 6 sections into one big prompt:

```
=== 1. FUNDING RULES ===
   "The funding program requires: projects must be in Germany,
    costs must not exceed €500k..."

=== 2. COMPANY INFORMATION ===
   "RobotCo GmbH makes automated welding systems. Founded 2010.
    50 employees. Website says: [scraped text]..."

=== 3. PROJECT TOPIC & DOMAIN RESEARCH ===
   "The project is about: laser weld seam tracking.
    Research found: [web search results about the technology]..."

=== 4. REFERENCE EXAMPLES ===
   "Here are past successful applications: [examples]..."

=== 5. STYLE GUIDE ===
   "Write in formal German. Avoid filler words. Use passive voice..."

=== 6. TASK ===
   "Now write these sections: Introduction, Technical Approach, Team..."
```

The AI reads all of this and writes the document sections.

### The Context Assembler — Research Before Writing

Before generating anything, the app does **background research** automatically.

This lives in `backend/app/services/context_assembler.py`.

It runs 5 stages (like a research assistant preparing a briefing):

```
Stage 1: Company Research
   → Look up what the company does (from profile or web search)

Stage 2: Funding Rules
   → Read the uploaded PDF guideline and extract the rules

Stage 3: Domain Research
   → Search the web for articles about the project's topic

Stage 4: Historical Examples
   → Find similar past applications from a knowledge base

Stage 5: Style Profile
   → Load the preferred writing style from past documents

Result: A "ProjectContext" — a research dossier saved to the database
```

This context is what gets fed into the prompt when AI generates the document.

---

## 6. Authentication — Who Are You?

You can't use the app without logging in. Here's how it works:

### Login
```
You type: email + password
  ↓
Backend checks: is the password correct?
  ↓
If yes: Backend creates a JWT token (like a wristband at an event)
  ↓
Frontend stores this token in localStorage (your browser remembers it)
  ↓
Every future request includes this token: "Here's my wristband!"
```

### What is a JWT Token?

A **JWT** (JSON Web Token) is a small piece of encoded text. It contains:
- Your email address
- When it was issued
- When it expires (after 24 hours)
- A secret signature so it can't be faked

Every API request the frontend makes includes this token in a header:
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6...
```

The backend checks this token on every request. If it's expired or fake → rejected.

### Who Can Sign Up?

Only email addresses ending in `@innovo-consulting.de` or `@aiio.de` can register.
This is enforced in `backend/app/schemas.py`.

---

## 7. The Project Lifecycle — From Zero to Document

Here's the complete journey a project takes:

```
┌─────────────────────────────────────────────────────┐
│  STATUS: "assembling"                               │
│  User just created the project.                     │
│  Background research is running.                    │
└────────────────────────┬────────────────────────────┘
                         │ (a few seconds later)
                         ↓
┌─────────────────────────────────────────────────────┐
│  STATUS: "ready"                                    │
│  Research is done. Project context saved.           │
│  User can now start generating the document.        │
└────────────────────────┬────────────────────────────┘
                         │ (user clicks "Generate")
                         ↓
┌─────────────────────────────────────────────────────┐
│  STATUS: "generating"                               │
│  AI is writing the document sections.               │
└────────────────────────┬────────────────────────────┘
                         │ (AI done)
                         ↓
┌─────────────────────────────────────────────────────┐
│  STATUS: "complete"                                 │
│  Document is written. User can edit, chat, export.  │
└─────────────────────────────────────────────────────┘
```

### How Does the Frontend Know When Research is Done?

It **polls** — it asks the backend every 2 seconds: "Are you done yet?"

```
Frontend: GET /projects/7  → { "status": "assembling" }  → wait 2s
Frontend: GET /projects/7  → { "status": "assembling" }  → wait 2s
Frontend: GET /projects/7  → { "status": "ready" }       → show workspace!
```

---

## 8. All the Moving Parts — File by File

### Backend Files

```
backend/
│
├── main.py
│   The starting point. When the server starts, this file runs.
│   It registers all the routes (API menu items).
│   It also sets up CORS (allows the frontend to talk to the backend).
│
├── app/
│   │
│   ├── models.py
│   │   Defines the database tables using Python classes.
│   │   Example: class Project: has id, user_email, company_name, status, ...
│   │
│   ├── schemas.py
│   │   Defines what data looks like when sent over HTTP.
│   │   Think of it as the "shape" of requests and responses.
│   │
│   ├── database.py
│   │   Sets up the connection to PostgreSQL.
│   │   Every request gets a "session" — a short-lived connection to the database.
│   │
│   ├── dependencies.py
│   │   Shared helpers injected into routes.
│   │   The most important: get_current_user() — reads the JWT token.
│   │
│   ├── jwt_utils.py
│   │   Creates and verifies JWT tokens.
│   │
│   ├── routers/
│   │   │   Each file here handles one group of API endpoints.
│   │   │
│   │   ├── auth.py          → /auth/login, /auth/register
│   │   ├── projects.py      → /projects (create, list, get)
│   │   ├── project_chat.py  → /projects/{id}/chat
│   │   ├── documents.py     → /documents (generate, chat, export) — VERY BIG FILE
│   │   ├── companies.py     → /companies (create, crawl website, upload audio)
│   │   ├── funding_programs.py → /funding-programs (create, upload guidelines)
│   │   └── templates.py     → /templates (custom document templates)
│   │
│   ├── services/
│   │   │   Business logic — the "thinking" layer.
│   │   │
│   │   ├── context_assembler.py   → runs the 5-stage research pipeline
│   │   ├── prompt_builder.py      → builds the letter sent to the AI
│   │   └── project_chat_service.py → handles chatbot conversations
│   │
│   ├── extraction.py         → asks AI to extract company facts from website text
│   ├── guidelines_processing.py → asks AI to extract rules from PDF text
│   ├── style_extraction.py   → asks AI to extract writing style patterns
│   ├── preprocessing.py      → transcribes audio (Whisper), crawls websites
│   ├── document_extraction.py → reads text out of PDF and DOCX files
│   ├── text_cleaning.py      → removes filler words and boilerplate
│   ├── file_storage.py       → uploads files to Supabase cloud storage
│   ├── processing_cache.py   → avoids doing the same work twice (caching)
│   └── observability.py      → logs what's happening (for debugging)
```

### Frontend Files

```
frontend/src/
│
├── App.tsx
│   The map of all pages. Defines which URL shows which page.
│   Example: /projects/:id → show ProjectWorkspacePage
│
├── main.tsx
│   The starting point. Loads the React app into the browser.
│
├── utils/api.ts
│   The ONLY place that talks to the backend.
│   All pages use this file to make requests.
│   It automatically adds the JWT token to every request.
│
├── contexts/
│   └── AuthContext.tsx    → holds login state (are you logged in? who are you?)
│
└── pages/
    │
    ├── LoginPage/          → the login form
    ├── DashboardPage/      → list of all your projects
    ├── NewProjectPage/     → form to create a new project
    ├── ProjectWorkspacePage/ → the main screen after a project is ready
    │                           shows context progress, sections, chat panel
    ├── EditorPage/         → the document editor (older flow)
    ├── CompaniesPage/      → manage company profiles
    ├── FundingProgramsPage/ → manage funding programs
    ├── TemplatesPage/       → browse document templates
    └── AlteVorhabensbeschreibungPage/ → admin tool for style references
```

---

## 9. External Services — Things We Borrow

The app uses several outside services:

### OpenAI API
- **What it is:** The AI that writes documents
- **Model used:** GPT-4o-mini (fast and affordable)
- **Also used for:** Transcribing audio (Whisper), generating text embeddings
- **Configured by:** `OPENAI_API_KEY` environment variable

### Supabase Storage
- **What it is:** Cloud file storage (like Google Drive for our files)
- **Used for:** Storing uploaded PDFs and audio files
- **Why not just save locally?** The server might restart and lose local files
- **Configured by:** `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_STORAGE_BUCKET`

### PostHog
- **What it is:** Analytics tracking (like Google Analytics but for internal use)
- **Used for:** Counting how many documents are generated, tracking errors
- **Configured by:** `POSTHOG_API_KEY`

### PostgreSQL
- **What it is:** The main database in production
- **In development:** Uses SQLite (a simpler local file database)
- **Migrations managed by:** Alembic (a tool that tracks database changes over time)

---

## 10. The Full Journey — One Example From Start to Finish

Let's trace every step when a user creates a project and generates a document.

### Step 1: User Opens the App

```
Browser loads → frontend/src/main.tsx starts React
App.tsx checks → is user logged in? (reads token from localStorage)
If no → redirect to /login
If yes → show /dashboard
```

### Step 2: User Logs In

```
LoginPage sends: POST /auth/login  { email: "alice@innovo-consulting.de", password: "..." }
                                    ↓
Backend (auth.py):
  → Find user in database by email
  → Hash the password and compare
  → If match: create JWT token (24-hour wristband)
  → Send back: { "token": "eyJ...", "email": "alice@..." }
                                    ↓
Frontend:
  → Saves token in localStorage
  → Sets AuthContext.isAuthenticated = true
  → Redirects to /dashboard
```

### Step 3: User Creates a Project

```
DashboardPage → User clicks "New Project"
Navigate to /projects/new

NewProjectPage shows form:
  Company name: "RobotCo GmbH"
  Funding program: [dropdown] WTT 2025
  Topic: "Laser-based weld seam tracking for automated welding"

User clicks "Create"
  ↓
Frontend sends: POST /projects
  Body: { "company_name": "RobotCo GmbH", "funding_program_id": 1, "topic": "Laser..." }
  Header: Authorization: Bearer eyJ...
                                    ↓
Backend (projects.py):
  → Verify JWT token → "Alice is authenticated ✓"
  → Create new row in "projects" table (status: "assembling")
  → Kick off background task: assemble_project_context(project_id=7)
  → Send back: { "id": 7, "status": "assembling", ... }
                                    ↓
Background task runs (context_assembler.py):
  Stage 1: Web search "RobotCo GmbH" → save company_profile_json
  Stage 2: Load WTT 2025 guidelines PDF → extract rules_json via AI
  Stage 3: Search web for "laser weld seam tracking" → save domain_research_json
  Stage 4: Look up similar past applications → save retrieved_examples_json
  Stage 5: Load writing style from past docs → save style_profile_json
  → Create ProjectContext row in database
  → Update project status to "ready"
```

### Step 4: Frontend Polls Until Ready

```
ProjectWorkspacePage loads for project 7
  Every 2 seconds:
    GET /projects/7 → { "status": "assembling" }  → show spinner
    GET /projects/7 → { "status": "assembling" }  → show spinner
    GET /projects/7 → { "status": "ready" }        → show workspace!
```

### Step 5: User Generates the Document

```
User sees workspace with section list (from template):
  [ ] Introduction
  [ ] Technical Approach
  [ ] Team & Resources
  [ ] Budget Plan
  ...

User clicks "Generate All Sections"
  ↓
Frontend sends: POST /documents/23/generate-content
                                    ↓
Backend (documents.py):
  → Load document #23
  → Load its ProjectContext (the research dossier)
  → PromptBuilder assembles the 6-block prompt
  → Call OpenAI API (GPT-4o-mini):
      "Here are the funding rules, here's the company, here's the topic research,
       here are examples, here's the style guide. Write these sections."
  → AI responds with JSON: { "intro": "RobotCo GmbH...", "approach": "...", ... }
  → Save each section's text into document.content_json
  → Send back the updated document
                                    ↓
Frontend displays the generated text for each section
```

### Step 6: User Edits via Chat

```
User clicks on "Technical Approach" section
User types: "Make this more technical and mention laser triangulation"
  ↓
Frontend sends: POST /documents/23/chat
  Body: { "section_id": "approach", "message": "Make this more technical..." }
                                    ↓
Backend:
  → Detect this is an EDIT request (not a question)
  → Build edit prompt:
      "Current text: [existing content]
       User instruction: <user_instruction>Make this more technical...</user_instruction>
       Rewrite this section."
  → Call OpenAI API → get rewritten text
  → Return suggestion (NOT saved yet)
                                    ↓
Frontend shows the suggested rewrite
User clicks "Accept"
  ↓
Frontend sends: POST /documents/23/chat/confirm
Backend saves the new text into document.content_json
```

### Step 7: Export

```
User clicks "Export as Word"
  ↓
Frontend sends: GET /documents/23/export?format=docx
                                    ↓
Backend:
  → Read all sections from document.content_json
  → Use python-docx library to build a Word file
  → Send the file as a download
                                    ↓
Browser downloads: "RobotCo_WTT2025_Application.docx"
```

**Done! The full cycle, end to end.**

---

## Quick Reference: Key Concepts

| Concept | Simple Explanation |
|---------|-------------------|
| Frontend | The web page you see in your browser |
| Backend | The server that does the actual work |
| Database | A giant organized filing cabinet for all data |
| API | A menu of actions the backend can perform |
| HTTP Request | A message the frontend sends to the backend |
| JWT Token | A wristband that proves you're logged in |
| Schema | The "shape" that data must follow |
| Model | A Python class that represents a database table |
| Router | A file that handles one group of API endpoints |
| Service | A file with business logic (not tied to HTTP) |
| Background Task | Work that runs after the response is sent (like research) |
| Context Assembler | The robot that does research before AI writes anything |
| Prompt Builder | The machine that writes the letter sent to the AI |
| Alembic | The tool that tracks changes to the database structure |
| SQLAlchemy | The Python library that talks to the database |
| React | The JavaScript framework that builds the web pages |
| FastAPI | The Python framework that handles web requests |
| GPT-4o-mini | The AI model that writes document content |

---

*Written for humans who want to understand how it all fits together.*
