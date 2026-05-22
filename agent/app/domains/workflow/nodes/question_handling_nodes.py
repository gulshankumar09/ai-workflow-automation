"""Question Handling Nodes for Conversational Workflows

This module handles general questions and provides helpful responses.
"""

from typing import Dict, Any

from ..graphs.states import WorkflowState
from ....shared import get_logger

logger = get_logger(__name__)


async def handle_question_node(state: WorkflowState) -> Dict[str, Any]:
    """Handle general questions and provide helpful responses.
    
    Args:
        state: Current conversational workflow state
        
    Returns:
        Updated state with helpful response
    """
    try:
        current_message = state.get("current_message", "")
        user_context = state.get("user_context", {})
        conversation_phase = state.get("conversation_phase", "")
        
        logger.info(f"Handling general question in phase: {conversation_phase}")
        
        # Analyze the question type
        message_lower = current_message.lower()
        
        # Help and capability questions
        if any(word in message_lower for word in ["help", "what can you do", "how do you work", "capabilities"]):
            response = _generate_help_response()

        # Status and progress questions
        elif any(word in message_lower for word in ["status", "progress", "where are we", "what's next"]):
            response = _generate_status_response(conversation_phase)

        # Technical questions about MCP or tools
        elif any(word in message_lower for word in ["mcp", "tools", "connect", "integrate"]):
            response = _generate_technical_response()

        # Troubleshooting questions
        elif any(word in message_lower for word in ["error", "problem", "issue", "not working", "failed"]):
            response = _generate_troubleshooting_response()

        # Pricing or limits questions  
        elif any(word in message_lower for word in ["cost", "price", "limit", "free"]):
            response = _generate_pricing_response()

        # Workflow examples or inspiration
        elif any(word in message_lower for word in ["example", "ideas", "inspiration", "what can i build"]):
            response = _generate_examples_response()

        # Security and privacy questions
        elif any(word in message_lower for word in ["security", "privacy", "safe", "data"]):
            response = _generate_security_response()

        # Default helpful response
        else:
            response = _generate_default_response(current_message)

        return {
            "assistant_response": response,
            "conversation_phase": conversation_phase,  # Maintain current phase
            "question_handled": True
        }
        
    except Exception as e:
        logger.error(f"Question handling failed: {e}")
        return {
            "assistant_response": "I'm sorry, I encountered an issue processing your question. Could you please rephrase it or ask something else?",
            "errors": [f"Question handling failed: {str(e)}"],
            "conversation_phase": state.get("conversation_phase", "intent_discovery")
        }


def _generate_help_response() -> str:
    """Generate a comprehensive help response."""
    return """🤖 **I'm Bili, your AI workflow assistant!** Here's what I can help you with:

**🔧 Workflow Creation:**
• Connect different platforms (GitHub, Slack, Notion, etc.)
• Automate repetitive tasks
• Create custom data flows
• Set up notifications and alerts

**⚡ What makes me special:**
• **Smart Tool Discovery** - I find the right tools automatically
• **MCP Integration** - Connect to 20+ external services
• **Real-time Execution** - Watch your workflows run live
• **Conversational** - Just tell me what you want in plain English

**💡 Try saying:**
• "Sync my GitHub issues to Slack"
• "When I get an email, create a Notion task"
• "Monitor my website and alert me if it's down"

What would you like to automate? 🚀"""


def _generate_status_response(conversation_phase: str) -> str:
    """Generate a status response based on current conversation phase."""
    phase_messages = {
        "greeting": "We're just getting started! Tell me what you'd like to automate.",
        "intent_discovery": "I'm understanding what you want to build. Keep telling me more!",
        "requirement_gathering": "I'm collecting the details I need. Almost ready to find tools!",
        "tool_discovery": "I'm discovering available tools for your workflow.",
        "tool_validation": "I'm validating that the tools I found will work properly.",
        "workflow_generation": "I'm creating your workflow based on your requirements.",
        "workflow_review": "Your workflow is ready for review! Take a look and let me know if you want changes.",
        "execution_complete": "Your workflow has been executed successfully!"
    }
    
    current_phase_msg = phase_messages.get(conversation_phase, "We're working on your workflow together!")
    return f"📍 **Current Status:** {current_phase_msg}\n\nIs there anything specific you'd like to know or change?"


def _generate_technical_response() -> str:
    """Generate a technical overview response about MCP and tools."""
    return f"""🔧 **Technical Overview:**

**MCP Integration:** 🟢 Available
• **Model Context Protocol** - Industry standard for AI tool integration
• **20+ External Services** - GitHub, Slack, Notion, APIs, and more
• **Real-time Connections** - Direct integration with your accounts

**Available Tool Categories:**
• 📊 **Data & Analytics** - Process, transform, and analyze data
• 🔗 **Communication** - Slack, Discord, email, notifications  
• 💾 **Storage & Files** - Cloud storage, file operations
• 🌐 **Web & APIs** - HTTP requests, webhooks, monitoring
• ⚙️ **Development** - GitHub, CI/CD, code operations

Want to see what specific tools are available for your use case?"""


def _generate_troubleshooting_response() -> str:
    """Generate a troubleshooting help response."""
    return """🔧 **Troubleshooting Help:**

If something isn't working:

1. **Check Connection** - Make sure your accounts are properly connected
2. **Review Permissions** - Verify I have access to the services you want to use
3. **Simplify First** - Try a simpler version of your workflow first
4. **Check Requirements** - Make sure all required information is provided

**Common Issues:**
• **Authentication** - Some services need API keys or OAuth
• **Permissions** - Make sure accounts have necessary permissions
• **Rate Limits** - Some services limit how often they can be called

**Quick Fixes:**
• **Restart** - Try describing your workflow again from the beginning
• **Be Specific** - Include exact channel names, repository names, etc.
• **Test Small** - Start with a simple 2-step workflow

Would you like me to help diagnose a specific issue?"""


def _generate_pricing_response() -> str:
    """Generate a pricing and limits response."""
    return """💰 **Usage & Limits:**

**Workflow Creation:** Unlimited
**Tool Discovery:** Unlimited  
**Basic Execution:** Free tier available
**Advanced Features:** Depends on connected services

**External Service Limits:**
• Each service (GitHub, Slack, etc.) has its own limits
• Most have generous free tiers
• I'll help you stay within limits

**No Hidden Costs:**
• I'll always tell you if something might incur charges
• You control which accounts and services are used

**What's Always Free:**
• Workflow design and planning
• Tool discovery and validation
• Simulated execution (testing)

Need help understanding limits for a specific service?"""


def _generate_examples_response() -> str:
    """Generate workflow examples and inspiration."""
    return """💡 **Workflow Ideas & Examples:**

**🔗 Popular Integrations:**
• **GitHub → Slack** - Notify team when issues are created
• **Email → Notion** - Turn emails into organized tasks
• **Calendar → Discord** - Share meeting updates with team
• **Jira → GitHub** - Sync tickets with development work

**⚡ Automation Categories:**

**📊 Data Sync:**
• Sync customer data between CRM and spreadsheets
• Backup important files to multiple cloud services
• Aggregate metrics from different tools

**🔔 Notifications:**
• Monitor website uptime and alert on issues
• Daily digest of important updates
• Alert when specific keywords appear in channels

**🤖 Task Automation:**
• Auto-create tickets from form submissions
• Schedule regular data backups
• Process and categorize incoming support requests

**🎯 Custom Workflows:**
• Content publishing pipeline
• Customer onboarding automation
• Development deployment workflows

Which category interests you most?"""


def _generate_security_response() -> str:
    """Generate a security and privacy response."""
    return """🔒 **Security & Privacy:**

**Your Data is Safe:**
• **No Storage** - I don't permanently store your workflow data
• **Encrypted** - All connections use industry-standard encryption
• **You Control** - You decide which accounts to connect

**MCP Security:**
• **Sandboxed** - Each tool runs in a secure environment
• **Permissions** - Only access what you explicitly allow
• **Auditable** - Full logs of what actions are performed

**Best Practices:**
• **API Keys** - Use tokens with minimal required permissions
• **Review** - Always review workflows before execution
• **Test** - Use simulation mode first

**Privacy:**
• **Conversation** - Not permanently stored
• **Credentials** - Never logged or stored
• **Execution** - You see exactly what happens

**Questions about specific services?**
Each connected service (GitHub, Slack, etc.) has its own security model that we respect and work within."""


def _generate_default_response(current_message: str) -> str:
    """Generate a default helpful response for unclear questions."""
    return f"""🤔 **Let me help!** 

I'm not sure I fully understand your question: "{current_message}"

**Here's how I can help:**
• **Create workflows** - Tell me what you want to automate
• **Answer questions** - About my capabilities, MCP integration, or workflow building
• **Troubleshoot** - Help fix issues with existing workflows
• **Explain** - How things work or what's possible

**Try asking:**
• "How do I connect GitHub to Slack?"
• "What tools do you have for data processing?"
• "Can you help me automate my daily standup?"
• "Show me some workflow examples"

What would you like to know more about? 🚀""" 