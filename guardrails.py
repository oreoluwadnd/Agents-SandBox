import chainlit as cl
import os
from typing import cast, List, Dict, Any
from datetime import datetime
import uuid
from supabase import create_client, Client
import json
from agents import Agent, Runner, RunConfig, InputGuardrailTripwireTriggered, OutputGuardrailTripwireTriggered
from input import math_guardrail
from output import math_output_guardrail
from setup import google_gemini_config

supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

@cl.on_chat_start
async def start():
    # Generate a unique session ID for this chat
    session_id = str(uuid.uuid4())
    
    cl.user_session.set("config", google_gemini_config)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("session_id", session_id)

    agent: Agent = Agent(
        name=" support agent",
        instructions="You are a customer support agent. You help customers with their questions.",
        input_guardrails=[math_guardrail],
        output_guardrails=[math_output_guardrail]
    )
    cl.user_session.set("agent", agent)

    # Check if we have a session ID provided to load previous chat
    query_params = cl.user_session.get("query_params", {})
    prev_session_id = query_params.get("session_id")
    
    if prev_session_id:
        # Load chat history from Supabase
        try:
            history = await load_chat_history(prev_session_id)
            if history:
                cl.user_session.set("chat_history", history)
                cl.user_session.set("session_id", prev_session_id)
                await cl.Message(content="Previous conversation loaded. How can I continue helping you?").send()
                return
        except Exception as e:
            print(f"Error loading previous chat: {str(e)}")
    
    await cl.Message(content=f"Welcome to the My AI Assistant! How can I help you today? (Your session ID: {session_id})").send()

async def save_chat_history(session_id: str, history: List[Dict[str, Any]]):
    """Save chat history to Supabase"""
    try:
        # Convert the history to a string for storage
        history_json = json.dumps(history)
        
        # Check if this session already exists
        response = supabase.table("chat_histories").select("id").eq("session_id", session_id).execute()
        
        if response.data and len(response.data) > 0:
            # Update existing record
            supabase.table("chat_histories").update({
                "history": history_json,
                "updated_at": datetime.now().isoformat()
            }).eq("session_id", session_id).execute()
        else:
            # Insert new record
            supabase.table("chat_histories").insert({
                "session_id": session_id,
                "history": history_json,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }).execute()
        
        return True
    except Exception as e:
        print(f"Error saving chat history: {str(e)}")
        return False

async def load_chat_history(session_id: str) -> List[Dict[str, Any]]:
    """Load chat history from Supabase"""
    try:
        response = supabase.table("chat_histories").select("history").eq("session_id", session_id).execute()
        
        if response.data and len(response.data) > 0:
            history_json = response.data[0]["history"]
            return json.loads(history_json)
        return []
    except Exception as e:
        print(f"Error loading chat history: {str(e)}")
        return []

@cl.on_message
async def main(message: cl.Message):
    """Process incoming messages and generate responses."""
    # Send a thinking message
    msg = cl.Message(content="Thinking...")
    await msg.send()

    agent: Agent = cast(Agent, cl.user_session.get("agent"))
    config: RunConfig = cast(RunConfig, cl.user_session.get("config"))
    session_id: str = cast(str, cl.user_session.get("session_id"))

    # Retrieve the chat history from the session.
    history = cl.user_session.get("chat_history") or []

    # Append the user's message to the history.
    history.append({"role": "user", "content": message.content})

    try:
        print("\n[CALLING_AGENT_WITH_CONTEXT]\n", history, "\n")
        result = Runner.run_sync(starting_agent=agent,
                                input=history,
                                run_config=config)

        print(f"RAW Result: {result}")
        response_content = result.final_output

        # Update the thinking message with the actual response
        msg.content = response_content
        await msg.update()

        # Update the session with the new history.
        updated_history = result.to_input_list()
        cl.user_session.set("chat_history", updated_history)
        
        # Save chat history to Supabase
        await save_chat_history(session_id, updated_history)

        # Optional: Log the interaction
        print(f"User: {message.content}")
        print(f"Assistant: {response_content}")

    except InputGuardrailTripwireTriggered:
        msg.content = "I can't help you with that. Please ask me something else."
        await msg.update()
        print("Math homework guardrail tripped")
    except OutputGuardrailTripwireTriggered:
        msg.content = "I can't help you with that. Please ask me something else."
        await msg.update()
        print("Math output guardrail tripped")
    except Exception as e:
        msg.content = f"Error: {str(e)}"
        await msg.update()
        print(f"Error: {str(e)}")