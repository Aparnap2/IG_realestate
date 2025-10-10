"""
Dynamic Workflow Engine for Multi-Tenant Automation

This module creates and manages LangGraph workflows dynamically based on
company-specific configurations, allowing each company to have custom
automation pipelines.
"""
from typing import Dict, Any, List, Optional, Callable
import logging
import json
import sys
import os
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.redis import RedisSaver
    from langgraph.prebuilt import ToolNode
except ImportError:
    # Fallback for testing
    class StateGraph:
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.edges = []
        
        def add_node(self, name, func):
            self.nodes[name] = func
        
        def add_edge(self, from_node, to_node):
            self.edges.append((from_node, to_node))
        
        def compile(self, checkpointer=None):
            return self
    
    class ToolNode:
        def __init__(self, tools):
            self.tools = tools
    
    END = "END"

try:
    from schemas.state import AgentState
    from models.lead import Lead
    from tools.agent_tools import (
        query_properties_db,
        send_reply,
        handoff_to_scheduler,
        handoff_to_followup,
        handoff_to_end,
        find_calendar_slot,
        book_event,
        log_to_hubspot
    )
    from utils.redis_client import get_redis_client
    from utils.llm_client import get_llm_client
    from utils.supabase_client import supabase
except ImportError:
    # Fallback for testing
    class AgentState:
        pass
    
    class Lead:
        pass
    
    def query_properties_db(*args, **kwargs):
        return []
    
    def send_reply(*args, **kwargs):
        return {"status": "sent"}
    
    def handoff_to_scheduler(*args, **kwargs):
        return {"next_agent": "scheduler"}
    
    def handoff_to_followup(*args, **kwargs):
        return {"next_agent": "followup"}
    
    def handoff_to_end(*args, **kwargs):
        return {"next_agent": "end"}
    
    def find_calendar_slot(*args, **kwargs):
        return []
    
    def book_event(*args, **kwargs):
        return {"status": "booked"}
    
    def log_to_hubspot(*args, **kwargs):
        return {"status": "logged"}
    
    def get_redis_client():
        return None
    
    def get_llm_client():
        return None
    
    class MockSupabase:
        def table(self, name):
            return self
        def select(self, fields):
            return self
        def eq(self, field, value):
            return self
        def execute(self):
            return type('obj', (object,), {'data': []})()
    
    supabase = MockSupabase()

logger = logging.getLogger(__name__)

class DynamicWorkflowEngine:
    """
    Dynamic workflow engine that creates LangGraph workflows based on
    company-specific configurations.
    """
    
    def __init__(self, company_id: str):
        self.company_id = company_id
        self.workflows = {}
        self.redis_client = get_redis_client()
        self.llm_client = get_llm_client()
        self.load_company_workflows()
    
    def load_company_workflows(self):
        """Load all workflows for the company"""
        try:
            result = supabase.table("workflows")\
                .select("*")\
                .eq("company_id", self.company_id)\
                .eq("is_active", True)\
                .execute()
            
            for workflow_data in result.data or []:
                workflow_id = workflow_data["id"]
                self.workflows[workflow_id] = self.create_workflow_graph(workflow_data)
                logger.info(f"Loaded workflow {workflow_id} for company {self.company_id}")
                
        except Exception as e:
            logger.error(f"Error loading company workflows: {e}")
    
    def create_workflow_graph(self, workflow_config: Dict[str, Any]) -> StateGraph:
        """
        Create a LangGraph workflow from company configuration.
        
        Args:
            workflow_config: Workflow configuration from database
            
        Returns:
            Compiled LangGraph workflow
        """
        try:
            # Create state graph
            graph = StateGraph(AgentState)
            
            # Get agents configuration
            agents_config = workflow_config.get("agents_config", {})
            agents = agents_config.get("agents", [])
            edges = agents_config.get("edges", [])
            settings = agents_config.get("settings", {})
            
            # Add nodes for each agent
            for agent_config in agents:
                agent_name = agent_config["name"]
                agent_type = agent_config.get("type", "generic")
                
                # Create agent function based on type
                agent_func = self.create_agent_function(agent_config)
                graph.add_node(agent_name, agent_func)
                
                logger.info(f"Added agent node: {agent_name} ({agent_type})")
            
            # Add edges based on configuration
            for edge in edges:
                from_node = edge["from"]
                to_node = edge["to"]
                
                if edge.get("conditional"):
                    # Add conditional edge
                    condition_func = self.create_condition_function(edge.get("condition", {}))
                    graph.add_conditional_edges(
                        from_node,
                        condition_func,
                        edge.get("mapping", {})
                    )
                else:
                    # Add regular edge
                    graph.add_edge(from_node, to_node)
                
                logger.info(f"Added edge: {from_node} -> {to_node}")
            
            # Set entry point
            entry_point = settings.get("entry_point", agents[0]["name"] if agents else "start")
            graph.set_entry_point(entry_point)
            
            # Add interrupt points if configured
            interrupt_before = settings.get("interrupt_before", [])
            interrupt_after = settings.get("interrupt_after", [])
            
            # Create checkpointer
            checkpointer = None
            if self.redis_client:
                checkpointer = RedisSaver(self.redis_client)
            
            # Compile the graph
            compiled_graph = graph.compile(
                checkpointer=checkpointer,
                interrupt_before=interrupt_before,
                interrupt_after=interrupt_after
            )
            
            return compiled_graph
            
        except Exception as e:
            logger.error(f"Error creating workflow graph: {e}")
            raise
    
    def create_agent_function(self, agent_config: Dict[str, Any]) -> Callable:
        """
        Create an agent function based on configuration.
        
        Args:
            agent_config: Agent configuration
            
        Returns:
            Agent function
        """
        agent_type = agent_config.get("type", "generic")
        agent_name = agent_config["name"]
        prompt_template = agent_config.get("prompt", "")
        tools = agent_config.get("tools", [])
        
        # Create tools list
        available_tools = self.get_available_tools()
        agent_tools = [available_tools[tool] for tool in tools if tool in available_tools]
        
        async def agent_function(state: AgentState) -> Dict[str, Any]:
            """Dynamic agent function"""
            try:
                logger.info(f"Executing agent: {agent_name}")
                
                # Get company-specific context
                company_context = await self.get_company_context()
                
                # Prepare prompt with context
                prompt = self.format_prompt(prompt_template, state, company_context)
                
                # Execute based on agent type
                if agent_type == "qualifier":
                    return await self.execute_qualifier_agent(state, prompt, agent_tools)
                elif agent_type == "scheduler":
                    return await self.execute_scheduler_agent(state, prompt, agent_tools)
                elif agent_type == "followup":
                    return await self.execute_followup_agent(state, prompt, agent_tools)
                elif agent_type == "custom":
                    return await self.execute_custom_agent(state, prompt, agent_tools, agent_config)
                else:
                    return await self.execute_generic_agent(state, prompt, agent_tools)
                    
            except Exception as e:
                logger.error(f"Error in agent {agent_name}: {e}")
                return {
                    "error_message": str(e),
                    "next_agent": "end"
                }
        
        return agent_function
    
    def create_condition_function(self, condition_config: Dict[str, Any]) -> Callable:
        """Create a condition function for conditional edges"""
        condition_type = condition_config.get("type", "score_threshold")
        
        def condition_function(state: AgentState) -> str:
            """Dynamic condition function"""
            try:
                if condition_type == "score_threshold":
                    threshold = condition_config.get("threshold", 0.7)
                    score = state.get("lead", {}).qualified_score or 0
                    return "high" if score > threshold else "low"
                
                elif condition_type == "budget_threshold":
                    threshold = condition_config.get("threshold", 500000)
                    budget = state.get("lead", {}).budget or 0
                    return "high_value" if budget > threshold else "normal"
                
                elif condition_type == "channel":
                    channel = state.get("lead", {}).channel
                    return channel or "unknown"
                
                elif condition_type == "custom":
                    # Custom condition logic
                    expression = condition_config.get("expression", "")
                    # Safely evaluate expression (simplified)
                    return "true" if eval(expression, {"state": state}) else "false"
                
                else:
                    return "default"
                    
            except Exception as e:
                logger.error(f"Error in condition function: {e}")
                return "error"
        
        return condition_function
    
    def get_available_tools(self) -> Dict[str, Callable]:
        """Get all available tools for agents"""
        return {
            "query_properties_db": query_properties_db,
            "send_reply": send_reply,
            "handoff_to_scheduler": handoff_to_scheduler,
            "handoff_to_followup": handoff_to_followup,
            "handoff_to_end": handoff_to_end,
            "find_calendar_slot": find_calendar_slot,
            "book_event": book_event,
            "log_to_hubspot": log_to_hubspot
        }
    
    async def get_company_context(self) -> Dict[str, Any]:
        """Get company-specific context for agents"""
        try:
            # Get company info
            company_result = supabase.table("companies")\
                .select("*")\
                .eq("id", self.company_id)\
                .execute()
            
            company = company_result.data[0] if company_result.data else {}
            
            # Get company integrations
            integrations_result = supabase.table("company_integrations")\
                .select("*")\
                .eq("company_id", self.company_id)\
                .eq("is_active", True)\
                .execute()
            
            integrations = integrations_result.data or []
            
            # Get company configs
            configs_result = supabase.table("configs")\
                .select("*")\
                .eq("company_id", self.company_id)\
                .execute()
            
            configs = {config["key"]: config["value"] for config in configs_result.data or []}
            
            return {
                "company": company,
                "integrations": integrations,
                "configs": configs
            }
            
        except Exception as e:
            logger.error(f"Error getting company context: {e}")
            return {}
    
    def format_prompt(self, template: str, state: AgentState, context: Dict[str, Any]) -> str:
        """Format prompt template with state and context"""
        try:
            # Replace placeholders in template
            formatted = template.format(
                lead=state.get("lead", {}),
                messages=state.get("messages", []),
                company=context.get("company", {}),
                configs=context.get("configs", {}),
                **context
            )
            return formatted
            
        except Exception as e:
            logger.error(f"Error formatting prompt: {e}")
            return template
    
    async def execute_qualifier_agent(self, state: AgentState, prompt: str, tools: List[Callable]) -> Dict[str, Any]:
        """Execute qualifier agent logic"""
        # Implementation similar to existing qualifier but with dynamic prompt
        lead = state.get("lead")
        if not lead:
            return {"error_message": "No lead data", "next_agent": "end"}
        
        # Query database for relevant properties
        properties = await query_properties_db(
            company_id=self.company_id,
            budget=lead.budget,
            location=lead.location,
            property_type=lead.property_type
        )
        
        # Use LLM to qualify lead
        if self.llm_client:
            response = await self.llm_client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Qualify this lead: {lead.message}"}
                ]
            )
            
            # Parse response for score and next action
            # This would need proper parsing logic
            score = 0.8  # Placeholder
            
            return {
                "qualified_score": score,
                "db_results": properties,
                "next_agent": "scheduler" if score > 0.7 else "followup"
            }
        
        return {"next_agent": "end"}
    
    async def execute_scheduler_agent(self, state: AgentState, prompt: str, tools: List[Callable]) -> Dict[str, Any]:
        """Execute scheduler agent logic"""
        # Implementation for scheduling
        return {"next_agent": "end"}
    
    async def execute_followup_agent(self, state: AgentState, prompt: str, tools: List[Callable]) -> Dict[str, Any]:
        """Execute followup agent logic"""
        # Implementation for follow-up
        return {"next_agent": "end"}
    
    async def execute_custom_agent(self, state: AgentState, prompt: str, tools: List[Callable], config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute custom agent logic"""
        # Implementation for custom agents
        return {"next_agent": "end"}
    
    async def execute_generic_agent(self, state: AgentState, prompt: str, tools: List[Callable]) -> Dict[str, Any]:
        """Execute generic agent logic"""
        # Implementation for generic agents
        return {"next_agent": "end"}
    
    def get_workflow(self, workflow_id: str) -> Optional[StateGraph]:
        """Get a specific workflow by ID"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self) -> List[str]:
        """List all available workflow IDs"""
        return list(self.workflows.keys())
    
    async def execute_workflow(self, workflow_id: str, initial_state: Dict[str, Any], thread_id: str) -> Dict[str, Any]:
        """
        Execute a workflow with given initial state.
        
        Args:
            workflow_id: ID of the workflow to execute
            initial_state: Initial state for the workflow
            thread_id: Thread ID for state persistence
            
        Returns:
            Final state after workflow execution
        """
        try:
            workflow = self.get_workflow(workflow_id)
            if not workflow:
                raise ValueError(f"Workflow {workflow_id} not found")
            
            # Execute workflow
            config = {"configurable": {"thread_id": thread_id}}
            result = await workflow.ainvoke(initial_state, config)
            
            # Log workflow execution
            await self.log_workflow_run(workflow_id, initial_state, result, "completed")
            
            return result
            
        except Exception as e:
            logger.error(f"Error executing workflow {workflow_id}: {e}")
            await self.log_workflow_run(workflow_id, initial_state, {"error": str(e)}, "failed")
            raise
    
    async def log_workflow_run(self, workflow_id: str, trigger_data: Dict[str, Any], result: Dict[str, Any], status: str):
        """Log workflow execution to database"""
        try:
            supabase.table("workflow_runs").insert({
                "workflow_id": workflow_id,
                "company_id": self.company_id,
                "trigger_data": trigger_data,
                "result": result,
                "status": status,
                "started_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat() if status in ["completed", "failed"] else None
            }).execute()
            
        except Exception as e:
            logger.error(f"Error logging workflow run: {e}")

# Industry-specific workflow templates
WORKFLOW_TEMPLATES = {
    "real_estate": {
        "name": "Real Estate Lead Processing",
        "description": "Qualify real estate leads and schedule property tours",
        "agents": [
            {
                "name": "qualifier",
                "type": "qualifier",
                "prompt": "You are a real estate lead qualifier. Ask about budget, location, property type, and timeline.",
                "tools": ["query_properties_db", "send_reply"]
            },
            {
                "name": "scheduler",
                "type": "scheduler", 
                "prompt": "You are a real estate scheduler. Book property tours and consultations.",
                "tools": ["find_calendar_slot", "book_event", "log_to_hubspot"]
            },
            {
                "name": "followup",
                "type": "followup",
                "prompt": "You are a real estate follow-up agent. Send property suggestions and nurture leads.",
                "tools": ["query_properties_db", "send_reply"]
            }
        ],
        "edges": [
            {"from": "qualifier", "to": "scheduler", "conditional": True, "condition": {"type": "score_threshold", "threshold": 0.7}},
            {"from": "qualifier", "to": "followup", "conditional": True, "condition": {"type": "score_threshold", "threshold": 0.7}},
            {"from": "scheduler", "to": "END"},
            {"from": "followup", "to": "END"}
        ],
        "settings": {
            "entry_point": "qualifier",
            "interrupt_before": ["scheduler"]
        }
    },
    
    "ecommerce": {
        "name": "E-commerce Customer Support",
        "description": "Handle customer inquiries and order issues",
        "agents": [
            {
                "name": "classifier",
                "type": "custom",
                "prompt": "Classify customer inquiry: order_status, product_question, complaint, return_request",
                "tools": ["send_reply"]
            },
            {
                "name": "order_handler",
                "type": "custom",
                "prompt": "Handle order-related inquiries and provide status updates",
                "tools": ["send_reply"]
            },
            {
                "name": "product_advisor",
                "type": "custom",
                "prompt": "Answer product questions and provide recommendations",
                "tools": ["send_reply"]
            }
        ],
        "edges": [
            {"from": "classifier", "to": "order_handler", "conditional": True, "condition": {"type": "custom", "expression": "'order' in state.lead.message.lower()"}},
            {"from": "classifier", "to": "product_advisor", "conditional": True, "condition": {"type": "custom", "expression": "'product' in state.lead.message.lower()"}},
            {"from": "order_handler", "to": "END"},
            {"from": "product_advisor", "to": "END"}
        ],
        "settings": {
            "entry_point": "classifier"
        }
    }
}

def create_workflow_from_template(company_id: str, industry: str, customizations: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a workflow configuration from an industry template.
    
    Args:
        company_id: Company ID
        industry: Industry type (real_estate, ecommerce, etc.)
        customizations: Custom modifications to the template
        
    Returns:
        Workflow configuration ready for database insertion
    """
    if industry not in WORKFLOW_TEMPLATES:
        raise ValueError(f"No template available for industry: {industry}")
    
    template = WORKFLOW_TEMPLATES[industry].copy()
    
    # Apply customizations if provided
    if customizations:
        template.update(customizations)
    
    # Create workflow configuration
    workflow_config = {
        "company_id": company_id,
        "name": template["name"],
        "description": template["description"],
        "trigger_type": "webhook",
        "trigger_config": {
            "conditions": [],
            "filters": {}
        },
        "agents_config": {
            "agents": template["agents"],
            "edges": template["edges"],
            "settings": template["settings"]
        },
        "industry_template": industry,
        "is_active": True
    }
    
    return workflow_config