"""LangGraph triage workflow definition.

Builds and compiles the full triage StateGraph with six nodes:
validate → label_source → label_event_type → label_priority →
label_environment → forward_to_rca.
"""

from langgraph.graph import StateGraph, END

from models import TriageState
from nodes.validate import validate_node, route_validation
from nodes.label_source import label_source_node
from nodes.label_event_type import create_label_event_type_node
from nodes.label_priority import create_label_priority_node
from nodes.label_environment import label_environment_node
from nodes.forward_to_rca import create_forward_to_rca_node


def build_triage_graph(llm, system_prompt: str, rca_url: str):
    """Build and compile the alert triage LangGraph workflow.

    Args:
        llm: A LangChain chat model instance used for event type and
            priority classification.
        system_prompt: The system prompt injected into LLM calls.
        rca_url: The URL of the downstream RCA agent.

    Returns:
        A compiled LangGraph ``CompiledStateGraph`` ready to be invoked.
    """
    graph = StateGraph(TriageState)

    # -- nodes --
    graph.add_node("validate", validate_node)
    graph.add_node("label_source", label_source_node)
    graph.add_node("label_event_type", create_label_event_type_node(llm, system_prompt))
    graph.add_node("label_priority", create_label_priority_node(llm, system_prompt))
    graph.add_node("label_environment", label_environment_node)
    graph.add_node("forward_to_rca", create_forward_to_rca_node(rca_url))

    # -- edges --
    graph.set_entry_point("validate")
    graph.add_conditional_edges(
        "validate",
        route_validation,
        {"label_source": "label_source", "__end__": END},
    )
    graph.add_edge("label_source", "label_event_type")
    graph.add_edge("label_event_type", "label_priority")
    graph.add_edge("label_priority", "label_environment")
    graph.add_edge("label_environment", "forward_to_rca")
    graph.add_edge("forward_to_rca", END)

    return graph.compile()
