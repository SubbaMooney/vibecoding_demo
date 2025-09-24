# API Specifications

## 1. MCP Protocol Tools

```yaml
# MCP Tool Definitions with Versioning
tools:
  rag_search:
    description: "Semantic search across documents"
    versions:
      v1.0:
        parameters:
          query: string
          limit: integer
          threshold: float
      v1.1:
        parameters:
          query: string
          limit: integer
          threshold: float
          filters: object
    fallback: REST API /api/v1/search

  rag_summarize:
    description: "Summarize documents"
    versions:
      v1.0:
        parameters:
          document_id: string
          summary_type: enum[executive, technical, bullets]
```

## 2. REST API Endpoints

```yaml
openapi: 3.0.0
paths:
  /api/v1/search:
    post:
      summary: "Semantic search with filters"
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                query:
                  type: string
                filters:
                  type: object
                limit:
                  type: integer
                  default: 10
      responses:
        200:
          description: "Search results"
          content:
            application/json:
              schema:
                $ref: "#/components/schemas/SearchResults"

  /api/v1/documents:
    post:
      summary: "Upload document"
      requestBody:
        content:
          multipart/form-data:
            schema:
              type: object
              properties:
                file:
                  type: string
                  format: binary
                metadata:
                  type: object
```

## 3. WebSocket Events

```typescript
// WebSocket Event Definitions
interface WSEvents {
  // Client -> Server
  'search:start': {
    query: string;
    streaming: boolean;
  };
  
  // Server -> Client
  'search:result': {
    chunk: SearchResult;
    isLast: boolean;
  };
  
  'processing:progress': {
    documentId: string;
    stage: 'extracting' | 'chunking' | 'embedding';
    progress: number;
  };
  
  'sync:conflict': {
    field: string;
    localValue: any;
    remoteValue: any;
    resolution: 'local' | 'remote' | 'merge';
  };
}
```

---
