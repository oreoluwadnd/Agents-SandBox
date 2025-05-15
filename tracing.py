import os
from openai import AsyncOpenAI
from agents import Agent, Runner, trace, set_default_openai_api, set_default_openai_client, set_trace_processors
from agents.tracing.processor_interface import TracingProcessor
from pprint import pprint
from dotenv import load_dotenv
import json
from datetime import datetime
from supabase import create_client, Client

load_dotenv()


supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)


class SupabaseTraceProcessor(TracingProcessor):
    def __init__(self):
        self.traces = []
        self.spans = []

    def on_trace_start(self, trace):
        self.traces.append(trace)
        print(f"Trace started: {trace.trace_id}")

    def on_trace_end(self, trace):
        trace_data = trace.export()
        print(f"Trace ended: {trace.trace_id}")
        
        
        try:
           
            trace_json = {
                "trace_id": trace_data.get("trace_id"),
                "name": trace_data.get("name"),
                "start_time": trace_data.get("start_time"),
                "end_time": trace_data.get("end_time"),
                "metadata": json.dumps(trace_data.get("metadata", {})),
                "created_at": datetime.now().isoformat()
            }
            
            # Insert into Supabase
            supabase.table("traces").insert(trace_json).execute()
            print(f"Trace {trace.trace_id} saved to Supabase")
        except Exception as e:
            print(f"Error saving trace to Supabase: {e}")

    def on_span_start(self, span):
        self.spans.append(span)
        print(f"Span started: {span.span_id}")

    def on_span_end(self, span):
        span_data = span.export()
        print(f"Span ended: {span.span_id}")
        
      
        try:
            
            span_json = {
                "span_id": span_data.get("span_id"),
                "trace_id": span_data.get("trace_id"),
                "name": span_data.get("name"),
                "start_time": span_data.get("start_time"),
                "end_time": span_data.get("end_time"),
                "metadata": json.dumps(span_data.get("metadata", {})),
                "parent_span_id": span_data.get("parent_span_id"),
                "created_at": datetime.now().isoformat()
            }
            
            # Insert into Supabase
            supabase.table("spans").insert(span_json).execute()
            print(f"Span {span.span_id} saved to Supabase")
        except Exception as e:
            print(f"Error saving span to Supabase: {e}")

    def force_flush(self):
        print("Forcing flush of trace data")

    def shutdown(self):
        print("=======Shutting down trace processor========")
       

BASE_URL = os.getenv("BASE_URL" ,"https://generativelanguage.googleapis.com/v1beta/openai/" )
API_KEY = os.getenv("GEMINI_API_KEY") 
MODEL_NAME = os.getenv("MODEL_NAME" , "gemini-2.0-flash")


if not BASE_URL or not API_KEY or not MODEL_NAME:
    raise ValueError("Please set BASE_URL, GEMINI_API_KEY, MODEL_NAME via env var or code.")


client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)

set_default_openai_client(client=client, use_for_tracing=True)
set_default_openai_api("chat_completions")


supabase_processor = SupabaseTraceProcessor()
set_trace_processors([supabase_processor])


async def main():
    agent = Agent(name="Tracing Agent", instructions="Perform example tasks.", model=MODEL_NAME)
    
    with trace("Tracing workflow"):
        first_result = await Runner.run(agent, "Start the task")
        second_result = await Runner.run(agent, f"Rate this result: {first_result.final_output}")
        print(f"Result: {first_result.final_output}")
        print(f"Rating: {second_result.final_output}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())