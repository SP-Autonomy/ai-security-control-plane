"""
AI Security Control Plane Dashboard
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# Configuration
API_URL = "http://localhost:8000"
st.set_page_config(page_title="AI Security Control Plane", page_icon="🛡️", layout="wide")

# Custom CSS
st.markdown("""
<style>
.success-badge {background-color: #28a745; color: white; padding: 5px 10px; border-radius: 5px;}
.warning-badge {background-color: #ffc107; color: black; padding: 5px 10px; border-radius: 5px;}
.danger-badge {background-color: #dc3545; color: white; padding: 5px 10px; border-radius: 5px;}
</style>
""", unsafe_allow_html=True)

# Helper functions
def fetch_data(endpoint):
    try:
        response = requests.get(f"{API_URL}{endpoint}", timeout=5)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None

def post_data(endpoint, data):
    try:
        response = requests.post(f"{API_URL}{endpoint}", json=data, timeout=10)
        return response.json(), response.status_code
    except Exception as e:
        return None, 500

# Title & Health
st.title("🛡️ AI Security Control Plane")

# Sidebar
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["📊 Overview", "🤖 Agents", "📜 Policies", "📋 Audit Trail", "📚 RAG Management", "📈 Posture"])

# Overview Page
if page == "📊 Overview":
    st.header("System Overview")
    agents = fetch_data("/api/agents") or []
    policies = fetch_data("/api/policies") or []
    events = fetch_data("/api/evidence") or []
    rag_stats = fetch_data("/api/rag/stats")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Active Agents", len([a for a in agents if a.get("status") == "active"]))
    col2.metric("Active Policies", len([p for p in policies if p.get("enabled")]))
    col3.metric("Events", len(events))
    col4.metric("RAG Docs", rag_stats.get("total_documents", 0) if rag_stats else 0)
    
    if events:
        st.subheader("Recent Events")
        df = pd.DataFrame([{
            "Time": e.get("timestamp", "")[:19],
            "Type": e.get("event_type", ""),
            "Agent": e.get("agent_id", "N/A"),
            "Actor": e.get("actor", "")
        } for e in events[-10:][::-1]])
        st.dataframe(df, use_container_width=True)

# Agents Page
elif page == "🤖 Agents":
    st.header("Agent Registry")
    
    with st.expander("➕ Register New Agent"):
        with st.form("new_agent"):
            col1, col2 = st.columns(2)
            name = col1.text_input("Name*")
            nhi_id = col1.text_input("NHI ID*")
            owner = col2.text_input("Owner*")
            budget = col2.number_input("Budget", min_value=100, value=10000)
            tools = st.multiselect("Tools", ["web_search", "calculator", "file_read"])
            
            if st.form_submit_button("Register"):
                data = {"name": name, "nhi_id": nhi_id, "owner": owner, "allowed_tools": tools, "budget_per_day": budget}
                result, status = post_data("/api/agents", data)
                if status == 201:
                    st.success(f"✅ Registered: {name}")
                    st.rerun()
                else:
                    st.error(f"❌ Failed")
    
    agents = fetch_data("/api/agents") or []
    for agent in agents:
        with st.expander(f"🤖 {agent.get('name')} (ID: {agent.get('id')})"):
            col1, col2 = st.columns(2)
            col1.write(f"**NHI:** {agent.get('nhi_id')}")
            col1.write(f"**Owner:** {agent.get('owner')}")
            col2.write(f"**Budget:** {agent.get('budget_per_day'):,}")
            col2.write(f"**Tools:** {', '.join(agent.get('allowed_tools', []))}")

# Policies Page
elif page == "📜 Policies":
    st.header("Policies")
    
    policies = fetch_data("/api/policies") or []
    for policy in policies:
        with st.expander(f"📜 {policy.get('name')} v{policy.get('version')}"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                enabled = policy.get("enabled")
                if enabled:
                    st.markdown('<span class="success-badge">ENABLED</span>', unsafe_allow_html=True)
                else:
                    st.markdown('<span class="danger-badge">DISABLED</span>', unsafe_allow_html=True)
                
                st.write(f"**Category:** {policy.get('category')}")
                st.write(f"**Description:** {policy.get('description')}")
            
            with col2:
                policy_id = policy.get("id")
                if enabled:
                    if st.button("Disable", key=f"dis_{policy_id}"):
                        requests.patch(f"{API_URL}/api/policies/{policy_id}/disable")
                        st.rerun()
                else:
                    if st.button("Enable", key=f"en_{policy_id}"):
                        requests.patch(f"{API_URL}/api/policies/{policy_id}/enable")
                        st.rerun()

# Audit Trail Page
elif page == "📋 Audit Trail":
    st.header("Audit Trail")
    
    events = fetch_data("/api/evidence") or []
    st.write(f"**Total Events:** {len(events)}")
    
    for event in events[::-1][:20]:
        icon = "📚" if "rag" in event.get("event_type", "") else "✅"
        with st.expander(f"{icon} {event.get('event_type')} - {event.get('timestamp', '')[:19]}"):
            st.write(f"**Agent:** {event.get('agent_id')}")
            st.write(f"**Actor:** {event.get('actor')}")
            st.write(f"**Trace:** {event.get('trace_id')}")
            metadata = event.get("metadata", {})
            if metadata:
                st.json(metadata)

# RAG Management Page
elif page == "📚 RAG Management":
    st.header("RAG Management")
    
    rag_stats = fetch_data("/api/rag/stats")
    if rag_stats:
        col1, col2 = st.columns(2)
        col1.metric("Documents", rag_stats.get("total_documents", 0))
        col2.metric("Sources", len(rag_stats.get("sources", [])))
    
    st.subheader("📤 Upload Document")
    with st.form("upload"):
        content = st.text_area("Content", height=200)
        source = st.selectbox("Source", ["internal_docs", "public_website"])
        validate = st.checkbox("Validate", value=True)
        
        if st.form_submit_button("Upload"):
            if content:
                data = {"content": content, "source": source, "validate": validate}
                result, status = post_data("/api/rag/documents", data)
                if status == 200:
                    st.success("✅ Uploaded")
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('detail')}")
    
    st.subheader("🔍 Query")
    with st.form("query"):
        query = st.text_input("Query")
        agent_id = st.number_input("Agent ID", min_value=1, value=1)
        
        if st.form_submit_button("Query"):
            if query:
                data = {"query": query, "agent_id": agent_id, "k": 3}
                result, status = post_data("/api/rag/query", data)
                if status == 200:
                    st.success(f"Found {result.get('count')} results")
                    for chunk in result.get("chunks", []):
                        st.write(chunk.get("text"))
                else:
                    st.error(f"Failed: {result.get('detail')}")

# Posture Page - FIXED: Shows ALL agents
elif page == "📈 Posture":
    st.header("Security Posture")
    
    # Get all agents
    agents = fetch_data("/api/agents") or []
    
    if not agents:
        st.info("No agents registered yet")
    else:
        # Calculate overall average
        total_score = 0
        scored_count = 0
        
        # Auto-calculate posture for agents without scores
        for agent in agents:
            agent_id = agent.get("id")
            
            # Try to get latest score
            latest = fetch_data(f"/api/posture/agent/{agent_id}/latest")
            
            if not latest:
                # No score exists, calculate it
                with st.spinner(f"Calculating posture for {agent.get('name')}..."):
                    calc_result = requests.post(f"{API_URL}/api/posture/calculate/{agent_id}")
                    if calc_result.status_code == 200:
                        latest = fetch_data(f"/api/posture/agent/{agent_id}/latest")
            
            if latest:
                total_score += latest.get("overall_score", 0)
                scored_count += 1
        
        # Display summary
        if scored_count > 0:
            avg_score = round(total_score / scored_count)
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Average Score", f"{avg_score}/100")
                st.progress(avg_score / 100)
            
            with col2:
                st.metric("Total Agents", len(agents))
                st.metric("Scored", scored_count)
        
        st.subheader("Agent Scores")
        
        # Show posture for each agent
        for agent in agents:
            agent_id = agent.get("id")
            agent_name = agent.get("name")
            
            # Get latest score
            latest = fetch_data(f"/api/posture/agent/{agent_id}/latest")
            
            if latest:
                score = latest.get("overall_score", 0)
                
                with st.expander(f"🤖 {agent_name} - Score: {score}/100"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Scores:**")
                        st.write(f"- Registry: {latest.get('registry_score', 0)}/20")
                        st.write(f"- Tools: {latest.get('tools_score', 0)}/20")
                        st.write(f"- Tracing: {latest.get('tracing_score', 0)}/20")
                        st.write(f"- DLP: {latest.get('dlp_score', 0)}/20")
                        st.write(f"- Policy: {latest.get('policy_score', 0)}/20")
                    
                    with col2:
                        failing = latest.get("failing_checks", [])
                        if failing:
                            st.write("**Failing Checks:**")
                            for check in failing:
                                st.write(f"- {check}")
                        
                        recs = latest.get("recommendations", [])
                        if recs:
                            st.write("**Recommendations:**")
                            for rec in recs:
                                st.write(f"- {rec.get('message', 'N/A')}")
                    
                    # Recalculate button
                    if st.button(f"Recalculate", key=f"calc_{agent_id}"):
                        result = requests.post(f"{API_URL}/api/posture/calculate/{agent_id}")
                        if result.status_code == 200:
                            st.success("✅ Calculated")
                            st.rerun()
            else:
                # No score yet
                with st.expander(f"🤖 {agent_name} - Not Scored"):
                    if st.button(f"Calculate Score", key=f"init_{agent_id}"):
                        result = requests.post(f"{API_URL}/api/posture/calculate/{agent_id}")
                        if result.status_code == 200:
                            st.success("✅ Calculated")
                            st.rerun()
                        else:
                            st.error("Failed to calculate")

st.sidebar.markdown("---")
st.sidebar.markdown("**AI Security Control Plane v1.0**")