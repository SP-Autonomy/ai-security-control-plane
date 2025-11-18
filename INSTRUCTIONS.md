# 📋 Complete Setup Instructions

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Starting Services](#starting-services)
5. [Verification](#verification)
6. [Usage Guide](#usage-guide)
7. [Troubleshooting](#troubleshooting)
8. [Advanced Configuration](#advanced-configuration)

---

## System Requirements

### **Minimum Requirements**

```
CPU: 4 cores
RAM: 8 GB
Storage: 10 GB free space
OS: Linux (Ubuntu 22.04+), macOS (12+), or Windows 11 (with WSL2)
```

### **Recommended Requirements**

```
CPU: 8+ cores
RAM: 16 GB
Storage: 20 GB free space (SSD preferred)
OS: Linux (Ubuntu 24.04)
```

### **Software Dependencies**

```
Python: 3.12 or higher
Ollama: Latest version
SQLite: 3.x
curl: For API testing
jq: For JSON parsing
```

---

## Installation

### **Step 1: Clone Repository**

```bash
# Clone the repository
git clone https://github.com/yourusername/ai-security-control-plane.git
cd ai-security-control-plane

# Verify files
ls -la
# Should see: control_plane/, gateway/, ui/, tests/, data/, requirements.txt
```

---

### **Step 2: Setup Python Environment**

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate  # Windows

# Verify Python version
python --version
# Should show: Python 3.12.x or higher

# Upgrade pip
pip install --upgrade pip
```

---

### **Step 3: Install Dependencies**

```bash
# Install all requirements
pip install -r requirements.txt --break-system-packages

# Verify key packages
pip list | grep -E "fastapi|streamlit|chromadb|sqlalchemy|ollama"

# Expected output:
# fastapi              0.104.1
# streamlit            1.28.1
# chromadb             0.4.18
# sqlalchemy           2.0.23
# ollama               0.1.6
```

**Note:** The `--break-system-packages` flag is needed on some systems. If you get an error, try without it.

---

### **Step 4: Setup Ollama**

#### **Install Ollama**

```bash
# Linux/macOS
curl -fsSL https://ollama.com/install.sh | sh

# Verify installation
ollama --version
```

#### **Start Ollama Server**

```bash
# Start Ollama (will run in background)
ollama serve

# In a new terminal, pull the model
ollama pull llama3.2:1b

# Verify model downloaded
ollama list
# Should show: llama3.2:1b
```

---

### **Step 5: Initialize Database**

```bash
# Navigate to control plane directory
cd control_plane

# Run database initialization
python -m api.init_db

# Expected output:
# Creating database at: /path/to/control_plane.db
# Creating tables...
# ✓ Tables created
# ✓ Default agent created
# ✓ 3 policies loaded
# ✓ 3 tools registered
# Database initialized successfully!

# Verify database created
ls -lh control_plane.db
# Should show file ~100KB

# Check tables
sqlite3 control_plane.db ".tables"
# Should show: agents decisions evaluation_results events policies posture_scores tools

# Check default data
sqlite3 control_plane.db "SELECT COUNT(*) FROM agents;"
# Should show: 1
sqlite3 control_plane.db "SELECT COUNT(*) FROM policies;"
# Should show: 3
sqlite3 control_plane.db "SELECT COUNT(*) FROM tools;"
# Should show: 3

cd ..
```

---

## Configuration

### **Environment Variables**

Create `.env` file in project root:

```bash
# Create .env file
cat > .env << 'EOF'
# Disable ChromaDB telemetry
CHROMA_TELEMETRY_DISABLED=true

# Ollama configuration
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b

# Database path
DATABASE_PATH=control_plane/control_plane.db

# API ports
CONTROL_PLANE_PORT=8000
GATEWAY_PORT=8001
DASHBOARD_PORT=8501
EOF

# Verify .env created
cat .env
```

---

## Starting Services

You'll need **a single terminal** to run all services.

### **AI Security Control Plane and Dashboard**

```bash
# Create and Activate virtual environment
python -m venv venv
source venv/bin/activate
```

```bash
# Run the control plane
make run
```

---

**Access Dashboard:**
Open browser: http://localhost:8501

---

## Verification

### **Step 1: Check All Services**

```bash
# Control plane
curl http://localhost:8000/health
# Expected: {"status":"healthy"}

# Gateway
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"gateway"}

# Dashboard
curl http://localhost:8501
# Expected: HTML page (Streamlit app)

# Ollama
curl http://localhost:11434/api/tags
# Expected: JSON with model list
```

---

### **Step 2: Test Basic Functionality**

```bash
# Test 1: List agents
curl http://localhost:8000/api/agents | jq
# Expected: Array with 1 agent (Test Agent)

# Test 2: List policies
curl http://localhost:8000/api/policies | jq length
# Expected: 3

# Test 3: RAG stats
curl http://localhost:8000/api/rag/stats | jq
# Expected: {"status":"success","total_documents":0,...}

# Test 4: Gateway LLM request
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2?","actor":"test@example.com","agent_id":1}' \
  | jq
# Expected: Response with "response", "trace_id", etc.
```

---

## Usage Guide

### **Dashboard Navigation**

#### **📊 Overview Tab**
- View system status
- Active agents count
- Active policies count
- Recent events
- Event distribution chart

#### **🤖 Agents Tab**
- Register new agents
- View agent details
- Check agent statistics
- Manage agent permissions

**Register New Agent:**
1. Expand "➕ Register New Agent"
2. Fill in:
   - Name: `Marketing Agent`
   - NHI ID: `nhi_marketing_001`
   - Owner: `marketing@company.com`
   - Budget: `5000`
   - Tools: Select from list (e.g., `web_search`)
3. Click "Register"
4. Agent appears in list

#### **📜 Policies Tab**
- View all policies
- Enable/disable policies
- View Rego code
- Check policy stats

**Toggle Policy:**
1. Expand policy (e.g., "DLP Guard")
2. Click "Disable" or "Enable" button
3. Policy status updates immediately

#### **📋 Audit Trail Tab**
- View all events
- Filter by agent, type
- Search events
- View event details

#### **📚 RAG Management Tab**
- Upload documents
- Query RAG system
- View statistics

**Upload Document:**
1. Go to "📤 Upload Document"
2. Paste content
3. Select source (e.g., `internal_docs`)
4. Check "Validate" ✓
5. Add title (optional)
6. Click "Upload"

**Query RAG:**
1. Go to "🔍 Query"
2. Enter query (e.g., "What is DLP?")
3. Set agent ID (e.g., `1`)
4. Click "Query"
5. View results

#### **📈 Posture Tab**
- View security scores for all agents
- See dimension breakdowns
- Get recommendations
- Recalculate scores

---

### **API Usage**

#### **Create Agent**

```bash
curl -X POST http://localhost:8000/api/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Marketing Agent",
    "nhi_id": "nhi_marketing_001",
    "owner": "marketing@company.com",
    "allowed_tools": ["web_search"],
    "budget_per_day": 5000,
    "environment": "production"
  }' | jq
```

#### **Upload RAG Document**

```bash
curl -X POST http://localhost:8000/api/rag/documents \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Data Loss Prevention (DLP) protects sensitive information...",
    "source": "internal_docs",
    "validate": true
  }' | jq
```

#### **Query RAG**

```bash
curl -X POST http://localhost:8000/api/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is DLP?",
    "agent_id": 1,
    "k": 3
  }' | jq
```

#### **Test DLP Redaction**

```bash
curl -X POST http://localhost:8001/ingress \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "My email is test@example.com",
    "actor": "user@example.com",
    "agent_id": 1
  }' | jq '.redactions_applied'
# Expected: ["EMAIL"]
```

#### **Calculate Posture Score**

```bash
curl -X POST http://localhost:8000/api/posture/calculate/1 | jq
```

---

### **Use Different LLM Model**

```bash
# Pull different model
ollama pull mistral

# Edit .env
OLLAMA_MODEL=mistral

# Or edit gateway/app.py directly
# Change: model="llama3.2:1b"
# To: model="mistral"

# Restart gateway
```

---

## Getting Help

### **Documentation**

- **README.md** - Project overview
- **RESULTS.md** - Test results and metrics
- **This file (INSTRUCTIONS.md)** - Setup guide

---

## Next Steps

After successful setup:

1. **Explore Dashboard** - http://localhost:8501
2. **Create Agents** - Add different agent types
3. **Upload Documents** - Test RAG security
4. **Check Posture** - Review security scores
5. **Review Audit Trail** - See logged events

---

*Setup Guide Version: 1.0.0*  
*Last Updated: November 2025*  