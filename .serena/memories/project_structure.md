# Project Structure Overview

## Root Directory Structure
```
/
├── backend/                    # Python backend services
├── frontend/                   # React TypeScript frontend
├── docs/                      # Project documentation
├── api/                       # API specifications (OpenAPI)
├── nginx/                     # Reverse proxy configuration
├── monitoring/                # Prometheus/Grafana configs
├── .bmad-core/               # BMad Method configuration
├── .claude-flow/             # Claude Flow swarm configs
├── .swarm/                   # Multi-agent swarm state
├── docker-compose.yml        # Development environment
├── docker-compose.prod.yml   # Production deployment
├── Makefile                  # Development commands
├── CLAUDE.md                 # Claude Code instructions
└── README.md                 # Project overview
```

## Backend Structure (`backend/`)
```
backend/
├── app/
│   ├── core/                 # Core modules (config, database, security)
│   │   ├── config.py        # Environment-based configuration
│   │   ├── database.py      # Database connection and models
│   │   ├── security.py      # Authentication and authorization
│   │   └── redis.py         # Redis cache configuration
│   └── __init__.py
├── requirements/             # Dependency management
│   ├── api.txt              # API Gateway dependencies
│   ├── mcp.txt              # MCP Server dependencies
│   ├── rag.txt              # RAG Engine dependencies
│   ├── sync.txt             # Sync Service dependencies
│   ├── accessibility.txt    # Accessibility Service dependencies
│   └── dev.txt              # Development dependencies
├── migrations/              # Database migrations (Alembic)
└── Dockerfile.*            # Service-specific Docker configurations
```

## Frontend Structure (`frontend/`)
```
frontend/
├── src/                     # Source code
├── public/                  # Static assets
├── package.json            # Node.js dependencies and scripts
└── Dockerfile              # Frontend container configuration
```

## Microservices Architecture
The backend consists of 5 separate services:
1. **API Gateway** (`Dockerfile.api`) - Main FastAPI application (Port 8000)
2. **MCP Server** (`Dockerfile.mcp`) - MCP Protocol handler (Port 8001)
3. **RAG Engine** (`Dockerfile.rag`) - Document processing and search
4. **Sync Service** (`Dockerfile.sync`) - CRDT-based synchronization
5. **Accessibility Service** (`Dockerfile.accessibility`) - Accessibility features

## Infrastructure Services
- **PostgreSQL**: Primary database (Port 5432)
- **Redis**: Cache and session store (Port 6379)
- **Qdrant**: Vector database for semantic search (Port 6333)
- **MinIO**: S3-compatible object storage (Port 9000)
- **Prometheus**: Metrics collection (Port 9090)
- **Grafana**: Monitoring dashboard (Port 3001)
- **Jaeger**: Distributed tracing (Port 16686)
- **Nginx**: Reverse proxy (Port 80/443)

## Development vs Production
- **Development**: Uses `docker-compose.yml` + `docker-compose.override.yml`
- **Production**: Uses `docker-compose.prod.yml`
- **Hot Reload**: Enabled for both backend and frontend in development
- **Volume Mounts**: Source code mounted for development, excluded in production