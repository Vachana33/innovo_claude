# Product Vision — Innovo AI Funding Application Platform

> **Audience:** Product managers, engineers, and AI agents making decisions about features and system design.
> **Purpose:** This document defines the product philosophy that guides all development decisions. When a technical choice has multiple valid options, prefer the one that best aligns with this vision.
> **Status:** Reflects client direction validated through user testing. 2026-03.

---

## The Core Problem

Writing a funding application requires combining three types of knowledge simultaneously:

1. **Company knowledge** — what the company does, its technology, its innovation capacity
2. **Program knowledge** — what the funding body requires, its rules, its evaluation criteria
3. **Writing craft** — how a successful application is structured and phrased in formal German

Consultants at Innovo spend most of their time on information assembly, not on the actual writing. They interview company contacts, gather documents, read guideline PDFs, and then try to synthesise everything into a coherent draft. This is slow, repetitive, and error-prone.

The old system automated the final step (writing) but left the first two steps manual. Users still had to navigate between entity screens, upload files to the right place, and connect all the pieces before generation could begin. The tool felt like a **document management system with AI bolted on**.

The goal is the opposite: an **AI assistant that already knows the domain**, where the user simply describes what they want to build.

---

## The Product Philosophy

### AI does the assembly. The user does the directing.

The user's job is to say: *"I want to write a WTT application for OKB Sondermaschinenbau GmbH. The project is about robot automation for weld seam tracking."*

The system's job is to:
- Find or gather everything it knows about that company
- Load the WTT guidelines and rules
- Retrieve relevant past applications as reference
- Research the technical domain if needed
- Build a complete draft automatically

The user then reviews, adjusts, and approves. They do not manage files, entities, or data structures.

### Minimal input, maximum context

The creation form asks for three things:
1. Company name or selection
2. Funding program selection
3. Project topic (one sentence)

Everything else — website, documents, transcripts, guidelines, style references — is gathered and assembled automatically. Optional uploads are available but never required.

If no company data exists, the system searches the web. If no style profile exists, it uses the system default. If no guidelines are loaded, it generates with the rules it has. The system degrades gracefully; it never blocks.

### The workspace is the product

Once a project is created, the user works in a single screen for the entire lifecycle of that application. They never navigate away to manage data. Sections are pre-populated. Context is visible. Chat is available at all times.

The metaphor is a ChatGPT conversation, not a filing system. The user talks to the system and the system builds the document.

### The system gets smarter over time

Every completed application is a potential training example for future ones. Every uploaded guideline enriches the knowledge base. The system accumulates institutional knowledge — about the funding programs, about the industries, about what successful applications look like — and automatically applies it to new projects.

This is the value of the knowledge base: not just retrieval, but compounding quality over time.

---

## User Flow

```
Login
  └─ Dashboard
        ├─ Recent projects (last 10)
        ├─ Search
        └─ [New Project]
              ├─ Company (select existing or type name)
              ├─ Funding Program (select from list)
              ├─ Topic (one sentence)
              └─ [Start Analysis]
                    └─ Project Workspace
                          ├─ Context panel (what the AI knows)
                          ├─ Section list (from program template)
                          ├─ Section editor
                          └─ AI chat (edit, ask, generate)
```

Navigation items the user sees: **Dashboard** and **Settings**.
Everything else — Companies, Funding Programs, Documents, Templates — is a background data structure accessible only through Settings or project configuration.

---

## What This Means for Development Decisions

### When adding a new feature, ask:

- Does this require the user to understand a new entity or data structure? If yes, find a way to make it invisible.
- Does this add a navigation item? It should not unless it is a primary workflow entry point.
- Does this require the user to perform a setup step before they can generate? If yes, automate it.
- Does this improve the quality of the AI's first draft without requiring user input? It belongs in the context assembly pipeline.

### When designing a new data model, ask:

- Is this a background data structure (assembled and managed by the system)? It should not be user-facing.
- Is this something the user directly creates and names? It might warrant a UI.
- Projects are user-created. Companies are user-created or auto-created. Everything else is assembled or derived.

### When making LLM changes, ask:

- Does this increase the information available to the model at generation time without increasing user burden? Good.
- Does this require the user to provide more input before generating? Bad.
- Does this change prompt wording? Test German output quality first.

---

## What We Are Not Building

- A document management system (that is the old design)
- A CRM or company database (companies are context sources, not the product)
- A template editor as a primary feature (templates are implementation detail)
- A general-purpose writing assistant (the domain is narrow: German public funding applications)
- A tool for companies to use directly (the users are Innovo consultants, not their clients)

---

## Success Criteria

A consultant should be able to go from a blank screen to a complete first draft of a Vorhabensbeschreibung in under **10 minutes** of active user time, given that the funding program guidelines are already loaded in the system.

The quality of the first draft should require fewer than **3 rounds of editing** before it is client-ready.

Users should not need to read a manual or receive training to use the primary workflow.
