import os
from dotenv import load_dotenv
from agents import Agent, Runner, AsyncOpenAI, OpenAIChatCompletionsModel
from agents import Agent, ItemHelpers, Runner, function_tool
from agents.run import RunConfig
import asyncio
from agents.tool import function_tool


load_dotenv()
gemini_api_key = os.getenv("GEMINI_API_KEY")



if not gemini_api_key:
    raise ValueError("GEMINI_API_KEY is not set. Please ensure it is defined in your .env file.")


external_client = AsyncOpenAI(
    api_key=gemini_api_key,
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


@function_tool("get_weather")
def get_weather(location: str, unit: str = "C") -> str:
  """
  Fetch the weather for a given location, returning a short description.
  """
  # Example logic
  return f"The weather in {location} is 22 degrees {unit}."
     

@function_tool("piaic_student_finder")
def student_finder(student_roll: int) -> str:
  """
    Find a student by their roll number.
  """
  data = {1: "Ali",
          2: "Ahmed",
          3: "Sara",
          4: "John",
          5: "Doe",
          6: "Jane",
          7: "Smith",
          8: "Emily",}

  return data.get(student_roll, "Not Found")

async def main():
    agent = Agent(
        name="Assistant",
        instructions="You are a helpful assistant.",
        model=model
    )

    result = Runner.run_streamed(agent, input="Please tell me 5 jokes.")
    print("=== Run starting ===")
    async for event in result.stream_events():
        # We'll ignore the raw responses event deltas
        if event.type == "raw_response_event":
            continue
        elif event.type == "agent_updated_stream_event":
            print(f"Agent updated: {event.new_agent.name}")
            continue
        elif event.type == "run_item_stream_event":
            if event.item.type == "tool_call_item":
                print("-- Tool was called")
            elif event.item.type == "tool_call_output_item":
                print(f"-- Tool output: {event.item.output}")
            elif event.item.type == "message_output_item":
                print(f"-- Message output:\n {ItemHelpers.text_message_output(event.item)}")
            else:
                pass 

if __name__ == "__main__":
    asyncio.run(main())
     

