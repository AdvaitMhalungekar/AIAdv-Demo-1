"""
Agentic chatbot layer for PrimeNest Realty using Groq.
Uses Groq with tool-calling to answer property queries.
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv
import database as db

load_dotenv(override=True)

# ─── Groq Client Setup ────────────────────────────────────────────────────────

_api_key = os.getenv("GROQ_API_KEY")
if not _api_key:
    print("[WARN] No GROQ_API_KEY found. Set one in .env or environment.")
else:
    print(f"[OK] Groq API key loaded (ends with ...{_api_key[-4:] if len(_api_key) > 4 else ''})")

client = Groq(api_key=_api_key)
MODEL_NAME = os.getenv("GROQ_MODEL", "qwen/qwen3-32b")
print(f"[OK] Groq model configured: {MODEL_NAME}")

# ─── Tool Definitions (OpenAI/Groq Format) ───────────────────────────────────

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_sale_properties",
            "description": "Search for properties available for SALE in the PrimeNest Realty database. Use this when the user wants to buy a property. Returns a list of matching properties with details like price, area, amenities, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "locality": {
                        "type": "string",
                        "description": "Locality/area name to search in (e.g., Baner, Hinjewadi, Kharadi, Wakad, Bavdhan, Hadapsar, Magarpatta, Balewadi, Viman Nagar, Pimple Saudagar)"
                    },
                    "configuration": {
                        "type": "string",
                        "description": "BHK configuration (e.g., '1 BHK', '2 BHK', '3 BHK', '4 BHK')"
                    },
                    "property_type": {
                        "type": "string",
                        "description": "Type of property (e.g., 'Apartment', 'Villa', 'Plot', 'Row House', 'Office')"
                    },
                    "min_price": {
                        "type": "integer",
                        "description": "Minimum price in INR (e.g., 5000000 for 50 lakhs)"
                    },
                    "max_price": {
                        "type": "integer",
                        "description": "Maximum price in INR (e.g., 10000000 for 1 crore)"
                    },
                    "builder": {
                        "type": "string",
                        "description": "Builder name to filter by"
                    },
                    "amenities": {
                        "type": "string",
                        "description": "Comma-separated list of amenities to filter by (e.g., 'Swimming Pool, Gym, EV Charging'). The search returns properties containing ALL of these amenities."
                    },
                    "status": {
                        "type": "string",
                        "description": "Property status: 'Available' or 'Reserved'"
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_rental_properties",
            "description": "Search for properties available for RENT in the PrimeNest Realty database. Use this when the user wants to rent a property. Returns matching rentals with rent, deposit, furnishing details, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "locality": {
                        "type": "string",
                        "description": "Locality/area name to search in (e.g., Baner, Hinjewadi, Kharadi, Wakad, Bavdhan, Hadapsar, Magarpatta, Balewadi, Viman Nagar, Pimple Saudagar)"
                    },
                    "configuration": {
                        "type": "string",
                        "description": "BHK/RK configuration (e.g., '1 BHK', '2 BHK', '3 BHK', '1 RK')"
                    },
                    "property_type": {
                        "type": "string",
                        "description": "Type of property (e.g., 'Apartment', 'Studio', 'Shop', 'Independent House')"
                    },
                    "min_rent": {
                        "type": "integer",
                        "description": "Minimum monthly rent in INR"
                    },
                    "max_rent": {
                        "type": "integer",
                        "description": "Maximum monthly rent in INR"
                    },
                    "furnishing": {
                        "type": "string",
                        "description": "Furnishing status: 'Fully Furnished', 'Semi Furnished', or 'Unfurnished'"
                    },
                    "pets_allowed": {
                        "type": "boolean",
                        "description": "Whether pets are allowed"
                    },
                    "preferred_tenant": {
                        "type": "string",
                        "description": "Tenant type preference: 'Family', 'Bachelors', 'Working Professionals', 'Students'"
                    },
                    "amenities": {
                        "type": "string",
                        "description": "Comma-separated list of amenities to filter by (e.g., 'Swimming Pool, Gym, EV Charging'). The search returns properties containing ALL of these amenities."
                    }
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_property_details",
            "description": "Get complete details of a specific property by its ID. Use this when the user asks about a particular property.",
            "parameters": {
                "type": "object",
                "properties": {
                    "property_id": {
                        "type": "string",
                        "description": "The property ID (e.g., 'SALE001', 'RENT015')"
                    }
                },
                "required": ["property_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_agent_contact",
            "description": "Get contact information for a sales or rental agent by their ID. Use this when the user wants to contact an agent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_id": {
                        "type": "string",
                        "description": "The agent ID (e.g., 'SA001', 'RA005')"
                    }
                },
                "required": ["agent_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_company_info",
            "description": "Get PrimeNest Realty company information including office address, phone, and email. Use when the user asks about the company or its contact details.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_policies",
            "description": "Get PrimeNest Realty policies including booking amount, brokerage rates, virtual tours, and site visit information.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_faqs",
            "description": "Get frequently asked questions and their answers. Use this when the user has a general question about the company's services.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]

# ─── System Prompt ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are PrimeNest AI, the friendly and knowledgeable customer support assistant for **PrimeNest Realty**, a premier real estate company based in Baner, Pune.

Your role:
- Help customers find properties for sale or rent based on their requirements
- Provide detailed property information including pricing, amenities, area, and more
- Answer questions about company policies, brokerage, booking process
- Connect customers with the right sales or rental agents
- Answer general FAQs about the company's services

Guidelines:
1. Always use the available search tools to find properties — NEVER make up property data
2. When presenting properties, format them clearly with key details (name, type, config, price/rent, locality, amenities)
3. Use Indian Rupee formatting (₹) for prices. Format lakhs and crores appropriately (e.g., ₹53 Lakhs, ₹1.5 Cr)
4. Be warm, professional, and proactive — suggest related options when relevant
5. If a search returns no results, suggest broadening the criteria
6. When showing multiple properties, present them in a numbered list for clarity
7. Always mention the property ID so the user can refer to it later
8. If the user wants to schedule a visit or talk to an agent, use the agent contact tool to provide the relevant agent's details
9. Keep responses concise but informative. Use bullet points and formatting for readability
10. If the user's query is ambiguous, ask clarifying questions (e.g., "Are you looking to buy or rent?")
11. You MUST call tools by using the formal tool-calling response format. Do NOT generate raw text tag structures like `<function=...>` or `<tool_call...>` yourself. Only use the tool-calling mechanism.
"""


# ─── Tool Executor ────────────────────────────────────────────────────────────

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


# ─── Chat Function ────────────────────────────────────────────────────────────

def chat(session_id: int, user_message: str) -> str:
    """
    Process a user message in an agentic loop:
    1. Load chat history from DB
    2. Send to Groq with tools
    3. Handle tool calls in a loop
    4. Return final assistant response
    """
    print(f"[CHAT] Using model: {MODEL_NAME}")
    # Load chat history
    history_rows = db.get_session_messages(session_id, limit=30)
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history_rows:
        # Standard roles are user, assistant
        role = msg["role"]
        messages.append({
            "role": role,
            "content": msg["content"]
        })

    # Add current user message
    messages.append({
        "role": "user",
        "content": user_message
    })

    # Save user message to DB
    db.save_message(session_id, "user", user_message)

    # Agentic loop — handle multiple rounds of tool calls
    max_iterations = 10
    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            tools=tools,
            temperature=0.0,
        )

        response_message = response.choices[0].message
        
        # Check if the model wants to call tools
        if response_message.tool_calls:
            # We must append the assistant's message (with tool_calls) to continue the conversation correctly
            messages.append(response_message)

            for tool_call in response_message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}

                print(f"[TOOL] {fn_name}({fn_args})")

                # Execute the tool
                result = execute_tool(fn_name, fn_args)

                # Append tool response message
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": fn_name,
                    "content": result
                })
            
            # Continue the loop to get final response
            continue

        # No tool calls — extract text response
        assistant_response = response_message.content
        if assistant_response:
            # Save assistant response to DB
            db.save_message(session_id, "assistant", assistant_response)

            # Auto-title the session if it's the first exchange
            db_messages = db.get_session_messages(session_id, limit=3)
            if len(db_messages) <= 2:
                # Generate a short title from the user message
                title = user_message[:50] + ("..." if len(user_message) > 50 else "")
                db.update_session_title(session_id, title)

            return assistant_response

        break

    fallback = "I apologize, but I'm having trouble processing your request right now. Could you please try rephrasing your question?"
    db.save_message(session_id, "assistant", fallback)
    return fallback
