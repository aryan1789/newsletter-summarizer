import asyncio

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

APP_NAME = "newsletter_curator"
USER_ID = "cron"
SESSION_ID = "weekly_run"


async def main() -> None:
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID,
    )

    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text="Run the weekly newsletter digest now.")],
        ),
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                print("Done:", event.content.parts[0].text)
        elif event.content and event.content.parts:
            part = event.content.parts[0]
            if hasattr(part, "text") and part.text:
                print(f"[{event.author}] {part.text[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
