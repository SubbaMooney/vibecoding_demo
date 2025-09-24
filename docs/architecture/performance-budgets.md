# Performance Budgets

## 1. Response Time Budgets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Search Query | 200ms | 500ms | 1s |
| Document Upload | 2s | 5s | 10s |
| Sync Operation | 100ms | 300ms | 500ms |
| UI Initial Load | 1s | 2s | 3s |

## 2. Resource Budgets

| Component | CPU | Memory | Storage |
|-----------|-----|---------|----------|
| API Gateway | 2 cores | 2GB | - |
| RAG Engine | 4 cores | 8GB | - |
| Vector DB | 8 cores | 16GB | 100GB SSD |
| PostgreSQL | 4 cores | 8GB | 50GB SSD |

---
