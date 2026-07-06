"""
Retell AI Custom LLM WebSocket handler for PrimeNest Realty Voice Agent.
Reuses the same Groq LLM and database tools as the text chatbot.

Protocol reference: https://docs.retellai.com/api-references/custom-llm-websocket
"""

import json
import asyncio
from fastapi import WebSocket, WebSocketDisconnect
from groq import Groq
import os
from dotenv import load_dotenv
import database as db

load_dotenv(override=True)

# ─── Groq Client (reuse same config as agent.py) ─────────────────────────────

_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=_api_key)
MODEL_NAME = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")

# ─── Tool Definitions (same as agent.py) ──────────────────────────────────────

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_sale_properties",
            "description": "Search for properties available for SALE in the PrimeNest Realty database. Use this when the user wants to buy a property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "locality": {"type": "string", "description": "Locality/area name (e.g., Baner, Hinjewadi, Kharadi)"},
                    "configuration": {"type": "string", "description": "BHK configuration (e.g., '2 BHK', '3 BHK')"},
                    "property_type": {"type": "string", "description": "Type of property (e.g., 'Apartment', 'Villa')"},
                    "min_price": {"type": "integer", "description": "Minimum price in INR"},
                    "max_price": {"type": "integer", "description": "Maximum price in INR"},
                    "builder": {"type": "string", "description": "Builder name"},
                    "amenities": {"type": "string", "description": "Comma-separated amenities (e.g., 'Swimming Pool, Gym')"},
                    "status": {"type": "string", "description": "Property status: 'Available' or 'Reserved'"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_rental_properties",
            "description": "Search for properties available for RENT in the PrimeNest Realty database. Use this when the user wants to rent a property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "locality": {"type": "string", "description": "Locality/area name (e.g., Baner, Hinjewadi, Kharadi)"},
                    "configuration": {"type": "string", "description": "BHK configuration (e.g., '1 BHK', '2 BHK')"},
                    "property_type": {"type": "string", "description": "Type of property (e.g., 'Apartment', 'Studio')"},
                    "min_rent": {"type": "integer", "description": "Minimum monthly rent in INR"},
                    "max_rent": {"type": "integer", "description": "Maximum monthly rent in INR"},
                    "furnishing": {"type": "string", "description": "Furnishing status: 'Fully Furnished', 'Semi Furnished', or 'Unfurnished'"},
                    "pets_allowed": {"type": "boolean", "description": "Whether pets are allowed"},
                    "preferred_tenant": {"type": "string", "description": "Tenant type: 'Family', 'Bachelors', 'Working Professionals'"},
                    "amenities": {"type": "string", "description": "Comma-separated amenities"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_property_details",
            "description": "Get complete details of a specific property by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {"type": "string", "description": "The property ID (e.g., 'SALE001', 'RENT015')"}
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_contact",
            "description": "Get contact information for a sales or rental agent by their ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {"type": "string", "description": "The agent ID (e.g., 'SA001', 'RA005')"}
                },
                "required": ["agent_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get PrimeNest Realty company information including office address, phone, and email.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_policies",
            "description": "Get PrimeNest Realty policies including booking amount, brokerage rates, and site visit info.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_faqs",
            "description": "Get frequently asked questions and their answers about the company's services.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# ─── Voice Agent System Prompt (optimized for spoken conversation) ─────────────

VOICE_SYSTEM_PROMPT = """You are PrimeNest AI, the friendly and knowledgeable voice assistant for **PrimeNest Realty**, a premier real estate company based in Baner, Pune.

You are currently on a PHONE CALL with a customer. Speak naturally and conversationally.

Your role:
- Help customers find properties for sale or rent based on their requirements
- Provide detailed property information including pricing, amenities, area, and more
- Answer questions about company policies, brokerage, booking process
- Connect customers with the right sales or rental agents
- Answer general FAQs about the company's services

Voice-specific guidelines:
1. Keep responses CONCISE and conversational — this is a phone call, not a text chat
2. Use natural spoken language, avoid markdown formatting, bullet points, or special characters
3. When listing properties, mention at most 2-3 key properties and ask if they want more details
4. Use Indian Rupee amounts spoken naturally (e.g., "fifty-three lakhs" not "₹53,00,000")
5. Always use the available search tools to find properties — NEVER make up property data
6. Be warm, professional, and proactive — suggest related options when relevant
7. If a search returns no results, suggest broadening the criteria
8. Always mention the property ID so the user can refer to it later
9. If the user's query is ambiguous, ask clarifying questions
10. You MUST call tools by using the formal tool-calling response format. Do NOT generate raw text tag structures.
11. Don't say things like "let me search" or "please wait" — just search and respond naturally
"""


# ─── Tool Executor (reused from agent.py) ─────────────────────────────────────

def execute_tool(function_name: str, function_args: dict) -> str:
    """Execute a tool function and return its result as a JSON string."""
    try:
        if function_name == "search_sale_properties":
            result = db.search_sale_properties(**function_args)
            if not result:
                return json.dumps({"message": "No sale properties found matching your criteria.", "results": []})
            return json.dumps({"message": f"Found {len(result)} sale properties.", "results": result}, default=str)

        elif function_name == "search_rental_properties":
            result = db.search_rental_properties(**function_args)
            if not result:
                return json.dumps({"message": "No rental properties found matching your criteria.", "results": []})
            return json.dumps({"message": f"Found {len(result)} rental properties.", "results": result}, default=str)

        elif function_name == "get_property_details":
            result = db.get_property_details(**function_args)
            if not result:
                return json.dumps({"message": "Property not found with the given ID."})
            return json.dumps({"property": result}, default=str)

        elif function_name == "get_agent_contact":
            result = db.get_agent_contact(**function_args)
            if not result:
                return json.dumps({"message": "Agent not found with the given ID."})
            return json.dumps({"agent": result})

        elif function_name == "get_company_info":
            result = db.get_company_info()
            return json.dumps({"company": result})

        elif function_name == "get_policies":
            result = db.get_policies()
            return json.dumps({"policies": result})

        elif function_name == "get_faqs":
            result = db.get_faqs()
            return json.dumps({"faqs": result})

        else:
            return json.dumps({"error": f"Unknown tool: {function_name}"})

    except Exception as e:
        return json.dumps({"error": str(e)})


# ─── Retell WebSocket Handler ─────────────────────────────────────────────────

async def handle_retell_websocket(websocket: WebSocket):
    """
    Handle the Retell AI Custom LLM WebSocket protocol.
    
    Retell connects here when a call starts. It sends JSON messages with:
    - interaction_type: "response_required" | "update_only" | "reminder_required"
    - transcript: list of {role, content} objects representing the conversation
    
    We respond with:
    - response_id: int (matching the request)
    - content: string (the agent's spoken response)
    - content_complete: bool (true when done streaming)
    - end_call: bool (true to hang up)
    """
    await websocket.accept()
    print("[VOICE] Retell WebSocket connected")

    # Track response IDs to handle interruptions
    current_response_id = 0

    try:
        # Send initial greeting when call connects
        initial_response = {
            "response_id": 0,
            "content": "Hello! Welcome to PrimeNest Realty. I'm your AI property assistant. How can I help you today? Are you looking to buy or rent a property in Pune?",
            "content_complete": True,
            "end_call": False
        }
        await websocket.send_json(initial_response)
        print("[VOICE] Sent initial greeting")

        while True:
            try:
                # Receive message from Retell
                data = await websocket.receive_json()
            except WebSocketDisconnect:
                print("[VOICE] WebSocket disconnected")
                break

            interaction_type = data.get("interaction_type", "")
            response_id = data.get("response_id", 0)
            current_response_id = response_id

            print(f"[VOICE] Received: interaction_type={interaction_type}, response_id={response_id}")

            if interaction_type == "update_only":
                # Transcript update — no response needed
                continue

            if interaction_type in ("response_required", "reminder_required"):
                # Build messages from transcript
                transcript = data.get("transcript", [])
                messages = [{"role": "system", "content": VOICE_SYSTEM_PROMPT}]

                for entry in transcript:
                    role = entry.get("role", "user")
                    content = entry.get("content", "")
                    if role == "agent":
                        messages.append({"role": "assistant", "content": content})
                    else:
                        messages.append({"role": "user", "content": content})

                # If reminder, add a nudge
                if interaction_type == "reminder_required":
                    messages.append({
                        "role": "user",
                        "content": "[The caller has been silent for a while. Gently check if they're still there or need help with anything.]"
                    })

                # Process with Groq (agentic loop for tool calls)
                try:
                    final_response = await _process_with_groq(messages)

                    # Check if this response is still relevant (not interrupted)
                    if current_response_id == response_id:
                        await websocket.send_json({
                            "response_id": response_id,
                            "content": final_response,
                            "content_complete": True,
                            "end_call": False
                        })
                        print(f"[VOICE] Sent response: {final_response[:80]}...")

                except Exception as e:
                    print(f"[VOICE] Error processing: {e}")
                    await websocket.send_json({
                        "response_id": response_id,
                        "content": "I apologize, I'm having a brief technical issue. Could you please repeat your question?",
                        "content_complete": True,
                        "end_call": False
                    })

    except Exception as e:
        print(f"[VOICE] WebSocket error: {e}")
    finally:
        print("[VOICE] WebSocket handler ended")


async def _process_with_groq(messages: list) -> str:
    """
    Process messages through Groq with tool calling support.
    Returns the final text response from the LLM.
    Runs synchronous Groq calls in a thread executor to avoid blocking the event loop.
    """
    max_iterations = 5  # Fewer iterations for voice — keep it fast

    for _ in range(max_iterations):
        # Run Groq API call in thread pool (it's synchronous)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                temperature=0.3,  # Slightly more natural for voice
            )
        )

        response_message = response.choices[0].message

        # Check if the model wants to call tools
        if response_message.tool_calls:
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                print(f"[VOICE-TOOL] {fn_name}({fn_args})")

                result = execute_tool(fn_name, fn_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": result
                })

            continue

        # No tool calls — return the text response
        assistant_response = response_message.content
        if assistant_response:
            return assistant_response

        break

    return "I'm sorry, I'm having trouble processing that. Could you try asking in a different way?"
