# Suggested Development Commands

## Essential Commands (Use these frequently)

### Development Environment
```bash
make help              # Show all available commands
make dev               # Start development environment with hot reload
make up                # Start all services in detached mode
make down              # Stop all services
make logs              # Show logs for all services
make health            # Check health of all services
```

### Development Workflow
```bash
make build             # Build all Docker containers
make clean             # Clean up containers and volumes
make clean-all         # Clean up everything including images
```

### Testing
```bash
make test              # Run all tests (backend + frontend)
make test-backend      # Run backend tests only (pytest)
make test-frontend     # Run frontend tests only (vitest)
```

### Code Quality
```bash
make lint              # Run linting for both frontend and backend
make lint-fix          # Fix linting issues automatically
make format            # Format code (Black + Prettier)
```

### Database Operations
```bash
make db-migrate        # Run database migrations
make db-reset          # Reset database (WARNING: deletes data)
```

### Production
```bash
make prod-build        # Build production images
make prod-up           # Start production environment
```

### Monitoring
```bash
make monitor           # Show service resource usage
```

## Direct Commands (Alternative to Makefile)

### Backend Development
```bash
cd backend && pip install -r requirements/dev.txt  # Install dependencies
cd backend && python -m pytest                     # Run tests
cd backend && python -m black .                    # Format code
cd backend && python -m mypy .                     # Type checking
```

### Frontend Development
```bash
cd frontend && npm install     # Install dependencies
cd frontend && npm run dev     # Start dev server
cd frontend && npm test        # Run tests
cd frontend && npm run lint    # Lint code
```

### System Commands for Darwin (macOS)
```bash
docker ps                      # List running containers
docker logs <container>        # View container logs
find . -name "*.py" -type f    # Find Python files
grep -r "pattern" .            # Search for patterns
ls -la                         # List files with details
```