# Task Completion Workflow

## When a Development Task is Completed

### 1. Code Quality Checks (MANDATORY)
Run these commands before considering any task complete:

```bash
# Run all linting and formatting checks
make lint              # Checks both backend and frontend
make format            # Formats code if needed
```

**Backend Specific:**
```bash
cd backend
python -m black --check .     # Check formatting
python -m mypy .              # Type checking
python -m flake8 .            # Linting
```

**Frontend Specific:**
```bash
cd frontend
npm run lint                  # ESLint checking
npm run type-check            # TypeScript checking
npm run format:check          # Prettier checking
```

### 2. Testing Requirements (MANDATORY)
All changes must pass existing tests and include new tests:

```bash
# Run all tests
make test              # Runs both backend and frontend tests

# Run tests individually
make test-backend      # pytest for Python
make test-frontend     # vitest for TypeScript/React
```

### 3. Health Checks (RECOMMENDED)
Verify the system is working correctly:

```bash
make health            # Check all service health endpoints
make dev               # Start development environment
```

Manually verify:
- Frontend: http://localhost:3000
- API Docs: http://localhost:8000/docs
- All services are running: `docker-compose ps`

### 4. Database Migrations (IF APPLICABLE)
If database schema changes were made:

```bash
make db-migrate        # Apply database migrations
```

### 5. Documentation Updates (IF APPLICABLE)
- Update README.md if new features or commands were added
- Update API documentation in `api/openapi.yaml`
- Add/update inline code comments for complex logic
- Update any relevant memory files if architecture changed

### 6. Git Workflow
```bash
git add .
git commit -m "descriptive commit message"
# Note: Do not push unless explicitly requested by user
```

## Performance Considerations
- Monitor resource usage: `make monitor`
- Check logs for errors: `make logs`
- Verify no memory leaks or performance degradation

## Accessibility Compliance
For frontend changes, ensure:
- WCAG AA compliance maintained
- Screen reader compatibility
- Keyboard navigation support
- Color contrast requirements met

## Security Checks
- No secrets or API keys in code
- Input validation and sanitization
- Authentication/authorization maintained
- SQL injection prevention (use SQLAlchemy properly)

## Definition of "Done"
A task is only complete when:
1. ✅ All code quality checks pass
2. ✅ All tests pass (existing + new)
3. ✅ Health checks confirm system stability
4. ✅ Documentation is updated
5. ✅ No security vulnerabilities introduced
6. ✅ Accessibility standards maintained