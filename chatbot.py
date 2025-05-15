import os
from dotenv import load_dotenv
from typing import cast
import chainlit as cl
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel, handoff
from agents.run import RunConfig, RunContextWrapper


load_dotenv()

gemini_api_key = os.getenv("GEMINI_API_KEY")


if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY is not set. Please ensure it is defined in your .env file.")







@cl.on_chat_start
async def start():
    external_client = AsyncOpenAI(
        api_key=os.getenv("GEMINI_API_KEY"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    model = OpenAIChatCompletionsModel(
        model="gemini-2.0-flash",
        openai_client=external_client
    )

    config = RunConfig(
        model=model,
        model_provider=external_client,
        tracing_disabled=True
    )


    def on_handoff(agent: Agent, ctx: RunContextWrapper[None]):
        agent_name = agent.name
        print("--------------------------------")
        print(f"Handing off to {agent_name}...")
        print("--------------------------------")
        # Send a more visible message in the chat
        cl.Message(
            content=f"🔄 **Handing off to {agent_name}...**\n\nI'm transferring your request to our {agent_name.lower()} who will be able to better assist you.",
            author="System"
        ).send()

    
    billing_agent = Agent(name="Billing Agent", instructions="You are a billing agent", model=model)
    refund_agent = Agent(name="Refund Agent", instructions="You are a refund agent", model=model)

    # Correct on_handoff function definition
    

    agent = Agent(
        name="Triage Agent",
        instructions="You are a triage agent",
        model=model,
        handoff_description="Please hand off to the appropriate agent.",
        handoffs=[
            handoff(billing_agent, on_handoff=lambda ctx: on_handoff(billing_agent, ctx)),
            handoff(refund_agent, on_handoff=lambda ctx: on_handoff(refund_agent, ctx))
        ]
    )

    # Set session variables
    cl.user_session.set("agent", agent)
    cl.user_session.set("config", config)
    cl.user_session.set("billing_agent", billing_agent)
    cl.user_session.set("refund_agent", refund_agent)
    cl.user_session.set("chat_history", [])

    await cl.Message(content="Welcome to the Emmanuel Assistant! How can I help you today?").send()


@cl.on_message
async def main(message: cl.Message):
    """Process incoming messages and generate responses."""

    msg = cl.Message(content="Thinking...")
    await msg.send()

    agent: Agent = cast(Agent, cl.user_session.get("agent"))
    config: RunConfig = cast(RunConfig, cl.user_session.get("config"))


    history = cl.user_session.get("chat_history") or []

   
    history.append({"role": "user", "content": message.content})

    try:
        result = Runner.run_sync(agent, history, run_config=config)

        response_content = result.final_output

    
        msg.content = response_content
        await msg.update()

      
        history.append({"role": "developer", "content": response_content})

       
        cl.user_session.set("chat_history", history)
        print(f"History: {history}")

    except Exception as e:
        msg.content = f"Error: {str(e)}"
        await msg.update()
        print(f"Error: {str(e)}")