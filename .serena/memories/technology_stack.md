# Technology Stack Summary

## Backend Stack
- **Language**: Python 3.11+
- **Web Framework**: FastAPI with Pydantic for API validation
- **Database**: PostgreSQL 15+ with SQLAlchemy ORM
- **Vector Database**: Qdrant v1.7.3 for semantic search
- **Cache/Session**: Redis 7+ for caching and session management
- **Object Storage**: MinIO (S3-compatible) for file storage
- **ML/AI**: Sentence-Transformers, LangChain, PyTorch
- **Document Processing**: PyPDF2, python-docx, markdown-it
- **Protocol**: MCP (Model Context Protocol) with abstraction layer

## Frontend Stack
- **Framework**: React 18+ with TypeScript
- **UI Library**: Mantine v7+ component library
- **State Management**: Zustand with CRDT support
- **Build Tool**: Vite for fast development and building
- **PWA**: Workbox for service workers and offline support
- **Routing**: React Router DOM v6
- **Data Fetching**: TanStack React Query with Axios
- **Testing**: Vitest with Testing Library

## Infrastructure Stack
- **Containerization**: Docker with Docker Compose
- **Reverse Proxy**: Nginx with SSL/TLS termination
- **Monitoring**: Prometheus + Grafana + Jaeger tracing
- **Development**: Hot reloading for both frontend and backend
- **Database Migration**: Alembic for PostgreSQL schema management

## Development Tools
- **Code Quality**: Black, isort, flake8, mypy, ESLint, Prettier
- **Testing**: Pytest (backend), Vitest (frontend), end-to-end testing
- **Documentation**: Sphinx for backend, Storybook for frontend components
- **Version Control**: Git with pre-commit hooks