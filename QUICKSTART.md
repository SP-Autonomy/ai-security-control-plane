# 🎯 Lab 04 - Final Fix & Testing Guide

## 🔧 STEP 1: Apply All Fixes

### 1.1 Stop Services
```bash
# Press Ctrl+C in terminal running make dev
```

### 1.2 Install python-dotenv
```bash
source venv/bin/activate
pip install python-dotenv
```

### 1.3 Replace Files

Download and replace these files:

1. **Gateway (Ollama + Tracing)**
   ```bash
   cp ~/Downloads/gateway_app_final.py gateway/app.py
   ```

2. **Control Plane (Better Tracing)**
   ```bash
   cp ~/Downloads/main_fixed.py control_plane/api/main.py
   ```

3. **Requirements (Add dotenv)**
   ```bash
   cp ~/Downloads/requirements_updated.txt requirements.txt
   pip install -r requirements.txt
   ```

### 1.4 Verify .env File

Check your `.env` file has these settings:

```bash
cat .env
```

Should contain:
```env
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b

# LLM Mode (false = use real Ollama)
USE_MOCK_LLM=false

# Tracing (true = enable OpenTelemetry)
TRACING_ENABLED=true

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8001

# Database
DATABASE_URL=sqlite:///./control_plane.db
```

If not, create it:
```bash
cat > .env << 'EOF'
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b

# LLM Mode (false = use real Ollama)
USE_MOCK_LLM=false

# Tracing (true = enable OpenTelemetry)
TRACING_ENABLED=true

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
GATEWAY_HOST=0.0.0.0
GATEWAY_PORT=8001

# Database
DATABASE_URL=sqlite:///./control_plane.db
EOF
```

---

## ✅ STEP 2: Verify Ollama is Running

```bash
# Check Ollama service
ollama list

# Should show:
# NAME                       ID              SIZE      MODIFIED    
# llama3.2:1b                baf6a787fdff    1.3 GB    ...

# Test Ollama directly
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.2:1b",
  "prompt": "Say hello",
  "stream": false
}'

# Should return JSON with "response" field
```

If Ollama isn't running:
```bash
ollama serve
```

---

## 🚀 STEP 3: Start Services

```bash
# Make sure venv is active
source venv/bin/activate

# Start all services
make dev
```

### Expected Output:

```
Starting AI Security Control Plane...

gateway_config              ollama_url='http://localhost:11434' 
                           ollama_model='llama3.2:1b' 
                           use_mock=False 
                           tracing_enabled=True

control_plane_config       tracing_enabled=True

telemetry_configured       exporter='console'

INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)

  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

**Key things to verify:**
- ✅ `use_mock=False` (using real Ollama!)
- ✅ `tracing_enabled=True` (tracing is on!)
- ✅ `ollama_model='llama3.2:1b'` (your model!)
- ✅ All three services started (8000, 8001, 8501)

---

## 🧪 STEP 4: Test Ollama Integration

### Test 1: Health Check
```bash
curl http://localhost:8001/health | jq
```

**Expected:**
```json
{
  "status": "healthy",
  "service": "gateway",
  "llm_backend": "ollama:llama3.2:1b",  // ← Your model!
  "ollama_url": "http://localhost:11434",
  "tracing_enabled": true
}
```

### Test 2: Simple Question
```bash
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is 2+2?",
    "actor": "test@example.com"
  }' | jq
```

**Expected (Real Ollama Response):**
```json
{
  "response": "The answer is 4.",  // ← Actual response, not mock!
  "model": "llama3.2:1b",          // ← Your model!
  "tokens_used": 45,                // ← Real tokens, not 9!
  "redactions_applied": [],
  "trace_id": "abc123...",          // ← Real trace ID!
  "latency_ms": 1234                // ← Real time, not 0!
}
```

**Check logs - should see:**
```
calling_real_ollama        model='llama3.2:1b' base_url='http://localhost:11434'
ollama_success            tokens=45 response_length=15
```

### Test 3: PII Redaction with Ollama
```bash
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "My SSN is 123-45-6789 and email is john@example.com. Help!",
    "actor": "test@example.com"
  }' | jq
```

**Expected:**
```json
{
  "response": "I'd be happy to help... [actual Ollama response]",
  "model": "llama3.2:1b",
  "tokens_used": 78,
  "redactions_applied": ["SSN", "EMAIL"],  // ← PII detected!
  "trace_id": "def456...",
  "latency_ms": 1567
}
```

---

## 📊 STEP 5: Verify Tracing

With `TRACING_ENABLED=true`, traces are exported to console (since no OTLP collector).

**Check logs after making requests:**

```
{
  "name": "ingress_request",
  "context": {
    "trace_id": "0x1234...",
    "span_id": "0x5678...",
  },
  "attributes": {
    "actor": "test@example.com",
    "model": "llama3.2:1b",
    "use_mock": false
  }
}
```

### To Set Up Full Tracing (Optional - Advanced)

If you want to visualize traces in Jaeger:

```bash
# Run Jaeger (in separate terminal)
docker run -d --name jaeger \
  -p 4318:4318 \
  -p 16686:16686 \
  jaegertracing/all-in-one:latest

# Update .env
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# Restart services
make dev

# View traces at: http://localhost:16686
```

---

## 🎯 STEP 6: Complete Test Suite

### 6.1 Create Test Agents
```bash
source venv/bin/activate

# Agent 1: Customer Support
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "customer-support",
    "nhi_id": "spiffe://demo.com/support",
    "owner": "Stilyan",
    "allowed_tools": ["search_kb", "create_ticket"],
    "environment": "production"
  }'

# Agent 2: Data Analyst
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "data-analyst",
    "nhi_id": "spiffe://demo.com/analyst",
    "owner": "Stilyan",
    "allowed_tools": ["query_db"],
    "environment": "development"
  }'

# Agent 3: Email Assistant
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "email-assistant",
    "nhi_id": "spiffe://demo.com/email",
    "owner": "Stilyan",
    "allowed_tools": ["send_email"],
    "environment": "staging"
  }'

# Verify
curl http://localhost:8000/api/agents | jq
```

### 6.2 Test Each Agent
```bash
# Test agent 1
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Help me reset my password",
    "actor": "user@example.com",
    "agent_id": 1
  }' | jq

# Test agent 2 with PII
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze sales data for SSN 123-45-6789",
    "actor": "analyst@example.com",
    "agent_id": 2
  }' | jq .redactions_applied

# Test agent 3
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Draft email about meeting tomorrow",
    "actor": "admin@example.com",
    "agent_id": 3
  }' | jq
```

### 6.3 Run Evaluation Suites
```bash
# Run all tests
python evals/run_suite.py --suite all --mode compare

# Expected results with Ollama:
# - Jailbreak: 9-10/10 (90-100%)
# - Exfiltration: 9-10/10 (90-100%)
# - Drift: 7-8/8 (87-100%, similarity 0.7-0.9)
```

### 6.4 Check Dashboard
Open http://localhost:8501

**Verify:**
- [ ] Live Traces tab shows all requests
- [ ] Redactions column shows PII detected
- [ ] Model column shows "llama3.2:1b"
- [ ] Latency is realistic (>100ms, not 0)
- [ ] Policies tab lists 3 policies
- [ ] Posture tab shows 3 agents with scores
- [ ] Can toggle policies on/off

---

## 📈 STEP 7: Generate Final Reports

### 7.1 Run Complete Evaluation
```bash
python evals/run_suite.py \
  --suite all \
  --mode compare \
  --output-report FINAL_EVALUATION_REPORT.txt \
  --output-json FINAL_EVALUATION_RESULTS.json
```

### 7.2 Export Database
```bash
# Backup database
cp control_plane.db control_plane_backup.db

# Export schema
sqlite3 control_plane.db ".schema" > database_schema.sql

# Export data
sqlite3 control_plane.db ".dump" > database_dump.sql
```

### 7.3 Generate Screenshots
Take screenshots of:
1. Dashboard - Live Traces tab (showing PII redactions)
2. Dashboard - Policies tab (showing 3 policies)
3. Dashboard - Posture tab (showing agent scores)
4. Terminal - Evaluation results
5. Terminal - Gateway logs showing Ollama calls

---

## ✅ FINAL DELIVERABLES CHECKLIST

### Code
- [ ] All 4 labs completed (Lab 01-04)
- [ ] Git repository with clean commit history
- [ ] README.md with architecture diagrams
- [ ] requirements.txt with all dependencies
- [ ] Makefile with commands
- [ ] .env.example (template without secrets)

### Documentation
- [ ] ARCHITECTURE.md explaining design decisions
- [ ] TESTING.md with test procedures
- [ ] EVALUATION_REPORT.txt with results
- [ ] API documentation (FastAPI auto-generated at /docs)

### Proof of Security Features
- [ ] PII redaction working (SSN, email, credit card, phone)
- [ ] Policy enforcement (toggle on/off)
- [ ] Agent registry with NHI identities
- [ ] Audit trail (events table)
- [ ] Posture scoring (0-100 scale)
- [ ] Tracing integration (OpenTelemetry)

### Test Results
- [ ] Jailbreak tests: >80% pass rate
- [ ] Exfiltration tests: >90% pass rate
- [ ] Drift tests: Similarity 0.7-0.9
- [ ] Integration tests passing
- [ ] Dashboard functional

### Framework Alignment
- [ ] NIST AI RMF mapping documented
- [ ] OWASP Agentic SecOps compliance
- [ ] MITRE ATLAS threat modeling

---

## 🎓 What You Built (Portfolio Summary)

**Project:** AI Security Control Plane  
**Purpose:** Production-grade governance for LLM applications

**Key Features:**
1. **Gateway Pattern** - All LLM requests proxied through security layer
2. **DLP** - Automatic PII detection and redaction (4 types)
3. **Policy-as-Code** - Rego policies enforced at runtime
4. **Agent Registry** - NHI-based identity management
5. **Observability** - OpenTelemetry tracing integration
6. **Posture Scoring** - Continuous security assessment (5 dimensions)
7. **Dashboard** - Real-time visibility and control
8. **Evaluation Framework** - Automated security testing

**Technical Stack:**
- FastAPI (async Python web framework)
- SQLite (structured audit logs)
- OpenTelemetry (distributed tracing)
- OPA/Rego (policy engine)
- Streamlit (dashboard)
- Ollama (local LLM)

**Compliance:**
- NIST AI RMF (Govern, Map, Measure, Manage)
- OWASP Agentic SecOps Lifecycle
- MITRE ATLAS Threat Modeling

**Metrics:**
- 2,500+ lines of production code
- 4 integrated security labs
- 28 automated security tests
- 90%+ test pass rate
- <50ms gateway latency overhead

---

## 🚀 Next Steps After Lab Completion

### For Portfolio/GitHub:
1. Clean up code comments
2. Add architecture diagrams (use draw.io or mermaid)
3. Create demo video (5-10 minutes)
4. Write detailed README with setup guide
5. Tag release: v1.0.0

### For Job Interviews:
Practice explaining:
- "Why separation of app code and security policies?"
- "How does the agent registry prevent unauthorized access?"
- "What's the delta between policies ON vs OFF?"
- "How would you extend this to support RAG?"
- "What's the performance overhead of the gateway?"

### For Further Learning:
1. Add RAG with ChromaDB (Lab 02 integration)
2. Implement real OPA policy server
3. Add Prometheus metrics
4. Create Kubernetes deployment manifests
5. Add authentication (OAuth2/SPIFFE)
6. Implement tool approval workflows

---

## 🆘 Troubleshooting

### Ollama Still Not Working?
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check gateway logs
grep "calling_real_ollama" <make_dev_output>

# Test directly
curl -X POST http://localhost:11434/api/generate -d '{
  "model": "llama3.2:1b",
  "prompt": "test",
  "stream": false
}'
```

### Tracing Not Working?
```bash
# Check if enabled in logs
grep "tracing_enabled" <make_dev_output>

# Should see: tracing_enabled=True

# Console traces appear after each request
grep "span_id" <make_dev_output>
```

### Dashboard Not Loading?
```bash
# Check port
netstat -tlnp | grep 8501

# Manual start
streamlit run ui/dashboard.py --server.address 0.0.0.0

# Check browser console for errors
```

---

## ✅ SUCCESS CRITERIA

You've completed Lab 04 successfully when:

- [x] Gateway uses Ollama (not mock)
- [x] Model shows "llama3.2:1b" in responses
- [x] Latency is realistic (>100ms)
- [x] PII gets redacted (SSN, email, etc.)
- [x] Tracing is enabled and working
- [x] Dashboard shows live data
- [x] Evaluation tests pass (>80%)
- [x] Can toggle policies on/off
- [x] Agents tracked in registry
- [x] All documentation complete

**Congratulations! You've built a production-grade AI Security Control Plane! 🎉**