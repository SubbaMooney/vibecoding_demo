# MCP RAG Server

A comprehensive semantic search and document management system with Model Context Protocol (MCP) support, featuring privacy-by-design architecture, cross-device synchronization, and advanced accessibility features.

## 🌟 Features

### Core Functionality
- **Semantic Search**: Advanced vector-based document search with hybrid (semantic + keyword) capabilities
- **Document Processing**: Support for PDF, DOCX, Markdown, and text files with intelligent chunking
- **MCP Protocol**: Full support for Model Context Protocol with version abstraction layer
- **Cross-Device Sync**: CRDT-based conflict-free synchronization across devices
- **Privacy-First**: GDPR-compliant with federated learning and data minimization

### User Experience
- **Progressive Web App**: Mobile-optimized with offline support
- **Accessibility**: WCAG AA compliant with screen reader, voice control, and keyboard navigation
- **Real-time Updates**: WebSocket-powered live search and processing status
- **Smart Onboarding**: Progressive disclosure with contextual help

### Technical Architecture
- **Hexagonal Architecture**: Protocol-agnostic design with pluggable adapters
- **Microservices**: Separate services for API, MCP, RAG, Sync, and Accessibility
- **Container-Ready**: Docker Compose for development and production deployment
- **Monitoring**: Comprehensive observability with Prometheus, Grafana, and distributed tracing

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)

### Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd mcp-rag-server
   ```

2. **Start the development environment**
   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Frontend: http://localhost:3000
   - API Documentation: http://localhost:8000/docs
   - MCP Server: http://localhost:8001
   - Database Admin: http://localhost:8080 (Adminer)
   - Monitoring: http://localhost:3001 (Grafana)

### Environment Variables

Create a `.env` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql://postgres:rag_password@postgres:5432/mcp_rag_db

# Redis
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=rag_redis_password

# Security
SECRET_KEY=your-super-secure-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Object Storage
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin123

# Vector Database
QDRANT_URL=http://qdrant:6333

# MCP Protocol
MCP_PROTOCOL_VERSION=1.0
```

## 📚 Documentation

### Architecture & Design
- [Product Requirements Document](docs/prd.md)
- [Technical Architecture](docs/technical-architecture.md)
- [Implementation Roadmap](docs/implementation-roadmap.md)
- [API Documentation](api/openapi.yaml)

### Development
- [Backend Development Guide](backend/README.md)
- [Frontend Development Guide](frontend/README.md)
- [Database Schema](backend/migrations/)
- [Docker Configuration](docker-compose.yml)

## 🏗️ Project Structure

```
├── docs/                          # Documentation
│   ├── prd.md                    # Product Requirements Document
│   ├── technical-architecture.md # Technical Architecture
│   └── implementation-roadmap.md # Development Roadmap
├── api/
│   └── openapi.yaml              # API Specification
├── backend/                      # Python Backend Services
│   ├── app/                      # Application Code
│   │   ├── core/                 # Core modules (config, database, etc.)
│   │   └── models/               # Database models
│   ├── requirements/             # Python dependencies
│   └── migrations/               # Database migrations
├── frontend/                     # React Frontend
│   ├── src/                      # Source code
│   ├── public/                   # Static assets
│   └── package.json             # Node.js dependencies
├── nginx/                        # Reverse proxy configuration
├── monitoring/                   # Prometheus & Grafana configs
├── docker-compose.yml           # Development environment
├── docker-compose.prod.yml      # Production deployment
└── README.md                    # This file
```

## 🧪 Testing

### Backend Tests
```bash
cd backend
pytest tests/ -v --cov=app
```

### Frontend Tests
```bash
cd frontend
npm test
npm run test:coverage
```

### Integration Tests
```bash
docker-compose -f docker-compose.test.yml up --abort-on-container-exit
```

## 🚀 Deployment

### Development
```bash
docker-compose up -d
```

### Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

## 🛠️ Technology Stack

### Backend
- **Language**: Python 3.11+
- **Framework**: FastAPI with Pydantic
- **Database**: PostgreSQL 15+ with SQLAlchemy
- **Vector DB**: Qdrant
- **Cache**: Redis 7+
- **ML/AI**: Sentence-Transformers, LangChain
- **Protocol**: MCP (Model Context Protocol)

### Frontend
- **Framework**: React 18+ with TypeScript
- **UI Library**: Mantine v7+
- **State Management**: Zustand with CRDT support
- **PWA**: Workbox for service workers
- **Accessibility**: ARIA, screen reader support

### Infrastructure
- **Containers**: Docker, Kubernetes
- **Monitoring**: Prometheus, Grafana, Jaeger
- **Proxy**: Nginx with rate limiting
- **Storage**: MinIO/S3 compatible

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow the established code style (Black for Python, Prettier for TypeScript)
- Write tests for new features
- Update documentation as needed
- Ensure accessibility compliance
- Follow security best practices

## 📋 Roadmap

The project follows a 16-sprint development plan:

- **Sprint 0-2**: Foundation and infrastructure
- **Sprint 3-4**: MCP protocol abstraction
- **Sprint 5-6**: Document processing pipeline
- **Sprint 7-8**: Vector search implementation
- **Sprint 9-10**: Progressive user interface
- **Sprint 11-12**: Sync and personalization
- **Sprint 13-14**: Accessibility and mobile
- **Sprint 15-16**: Production hardening

See [Implementation Roadmap](docs/implementation-roadmap.md) for details.

## 🔒 Security

- **Privacy-by-Design**: Email hashing, query anonymization
- **GDPR Compliance**: Data retention policies, user consent
- **Authentication**: JWT with refresh tokens
- **Rate Limiting**: Per-endpoint limits with Redis backend
- **Input Validation**: Comprehensive sanitization and validation
- **HTTPS**: TLS encryption for all communications

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the [docs/](docs/) directory
- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions for questions
- **Security**: Email security@example.com for security issues

## 🙏 Acknowledgments

- **MCP Protocol**: Model Context Protocol specification
- **Qdrant**: Vector similarity search engine
- **Mantine**: React components library
- **FastAPI**: Modern Python web framework

---

Built with ❤️ for semantic search and document management