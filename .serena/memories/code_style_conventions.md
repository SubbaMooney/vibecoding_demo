# Code Style and Conventions

## Python Backend Conventions

### Code Formatting
- **Formatter**: Black (line length: 88 characters)
- **Import Sorting**: isort with Black compatibility
- **Linting**: flake8 + mypy for type checking
- **Security**: bandit for security linting

### Python Style Guidelines
- **Type Hints**: Mandatory for all function signatures and class attributes
- **Docstrings**: Google-style docstrings for all modules, classes, and functions
- **Naming Conventions**:
  - Variables/functions: `snake_case`
  - Classes: `PascalCase`
  - Constants: `UPPER_SNAKE_CASE`
  - Private attributes: `_leading_underscore`

### Configuration Management
- Use Pydantic `BaseSettings` for environment-based configuration
- Environment variables in `UPPER_CASE` format
- Configuration validation with Pydantic validators
- Example from `backend/app/core/config.py`:
  ```python
  class Settings(BaseSettings):
      app_name: str = "MCP RAG Server"
      secret_key: str = Field(..., env="SECRET_KEY")
  ```

### FastAPI Patterns
- Use dependency injection for database sessions, authentication
- Route handlers should have proper status codes and response models
- Use Pydantic schemas for request/response validation
- Follow RESTful API design principles

## Frontend TypeScript Conventions

### Code Formatting
- **ESLint**: TypeScript-specific rules with React hooks plugin
- **Prettier**: Automatic code formatting
- **Type Safety**: Strict TypeScript configuration enabled

### React/TypeScript Patterns
- **Components**: Functional components with TypeScript interfaces
- **State Management**: Zustand for global state, React hooks for local state
- **File Structure**: Co-located component files with tests
- **Accessibility**: jsx-a11y plugin for accessibility compliance

### Naming Conventions
- **Components**: `PascalCase` (e.g., `DocumentUpload.tsx`)
- **Hooks**: `camelCase` starting with `use` (e.g., `useDocumentSearch`)
- **Types/Interfaces**: `PascalCase` with descriptive names
- **Files**: `kebab-case` for utilities, `PascalCase` for components

## General Development Guidelines

### Documentation
- README files for each major directory
- Inline comments for complex business logic
- API documentation using OpenAPI/Swagger
- Storybook for component documentation

### Testing Standards
- **Backend**: pytest with fixtures and mocks
- **Frontend**: Vitest with Testing Library
- **Coverage**: Minimum 80% code coverage
- **Integration**: End-to-end tests for critical user flows

### Git Workflow
- Feature branches from main
- Descriptive commit messages
- Pre-commit hooks for code quality
- Pull request reviews required