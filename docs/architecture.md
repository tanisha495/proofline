# ProofLine Architecture

## Overview

High-level architecture of the ProofLine pre-publication brand-governance platform.

## Review Engine (Four Steps)

### 1. Document Ingestion
<!-- Parse uploaded documents (.docx, .pdf, plain text) into structured text. -->

### 2. Guideline & Fact Checking
<!-- Compare extracted text against organisation rules, facts, and terminology. -->

### 3. Finding Generation
<!-- Produce cited Findings with severity, confidence, and source references. -->

### 4. Human Review & Approval
<!-- Route findings through a review workflow with comments, edits, and final approval. -->

## Data Model

<!-- Entity-relationship overview: Organisations, Users, Drafts, Versions, Findings, Claims, Comments, Approvals. -->

## Security and Privacy

<!-- JWT authentication, role-based access (Creator, Reviewer, Admin), organisation-level data isolation, audit logging. -->

## AI Services Used

<!-- LLM-based review engine (model configurable via LLM_MODEL). MOCK_AI flag for development. All AI outputs are suggestions; humans make final decisions. -->

