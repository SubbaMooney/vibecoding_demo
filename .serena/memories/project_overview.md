# MCP RAG Server Project Overview

## Project Purpose
MCP RAG Server is a comprehensive semantic search and document management system with Model Context Protocol (MCP) support. The system features:
- Advanced vector-based document search with hybrid (semantic + keyword) capabilities
- Document processing for PDF, DOCX, Markdown, and text files
- MCP Protocol support with version abstraction layer
- Cross-device synchronization using CRDT-based conflict-free synchronization
- Privacy-first design with GDPR compliance and federated learning
- Progressive Web App with offline support and WCAG AA accessibility compliance

## Architecture
The system uses a microservices architecture with hexagonal design patterns:
- **Protocol-agnostic core** with pluggable adapters
- **Multi-container deployment** with Docker Compose orchestration
- **Separate services**: API Gateway, MCP Server, RAG Engine, Sync Service, Accessibility Service
- **Progressive Web App** frontend with offline capabilities

## Development Status
This is an active development project following a 16-sprint roadmap. The project structure is fully established with comprehensive infrastructure, but implementation is in progress using BMad Method (AI-driven agile development) with multi-agent swarms.

## Key Business Value
- Semantic document search and management
- Cross-platform synchronization
- Privacy-by-design with federated learning
- Accessibility compliance for inclusive user experience
- Modern web technologies with offline-first approach