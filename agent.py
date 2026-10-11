"""Agentic AI agent: Gemini plans -> calls tools -> observes -> repeats until done."""
import os
import sys

from dotenv import load_dotenv
from google import genai
from google.genai import types

from tools import REGISTRY, TOOL_SCHEMAS

load_dotenv()
MODEL = "gemini-3.8-flash"
MAX_STEPS = 8  # safety cap on the reasoning loop

SYSTEM = ("You are an autonomous assistant. Break the user's goal into steps, "
          "use tools when they help, check their results, and only give a final "
          "answer once the goal is fully done. Be concise.")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
config = types.GenerateContentConfig(
    system_instruction=SYSTEM,
    tools=[types.Tool(function_declarations=TOOL_SCHEMAS)],
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
)


def run_agent(goal: str, history: list | None = None) -> tuple[str, list]:
    contents = history or []
    contents.append(types.Content(role="user", parts=[types.Part(text=goal)]))

    for step in range(1, MAX_STEPS + 1):
        resp = client.models.generate_content(model=MODEL, contents=contents, config=config)
        msg = resp.candidates[0].content
        contents.append(msg)

        calls = [p.function_call for p in msg.parts if p.function_call]
        if not calls:  # no tool needed -> final answer
            return resp.text, contents

        results = []
        for c in calls:
            args = dict(c.args or {})
            print(f"  [step {step}] 🔧 {c.name}({args})")
            out = REGISTRY[c.name](**args) if c.name in REGISTRY else "Unknown tool"
            print(f"           ↳ {str(out)[:150]}")
            results.append(types.Part.from_function_response(name=c.name, response={"result": out}))
        contents.append(types.Content(role="user", parts=results))

    return "Stopped: hit max steps.", contents


if __name__ == "__main__":
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit("Set GEMINI_API_KEY in .env first.")
    print("Agent ready. Type a goal (or 'exit').\n")
    history = []
    while True:
        goal = input("You: ").strip()
        if goal.lower() in {"exit", "quit"}:
            break
        if not goal:
            continue
        answer, history = run_agent(goal, history)
        print(f"\nAgent: {answer}\n")
