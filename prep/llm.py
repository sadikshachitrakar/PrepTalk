"""Ask gpt-oss on Groq for JSON that always matches a schema."""

import os

from groq import AsyncGroq
from pydantic import BaseModel, ConfigDict

# Each Groq model has its own free limits, so the quick jobs and the planner
# use different models and don't eat into each other's tokens per minute.
FAST_MODEL = "openai/gpt-oss-20b"
SMART_MODEL = "openai/gpt-oss-120b"


class Strict(BaseModel):
    """Base for every schema: no extra keys, which Groq's strict mode requires."""

    model_config = ConfigDict(extra="forbid")


async def ask_json(
    instructions: str, text: str, schema: type[BaseModel], model=FAST_MODEL, effort="low"
):
    """Send instructions plus text, and get back an instance of `schema`."""
    # max_retries: if you hit a free per-minute limit, wait and try again.
    async with AsyncGroq(api_key=os.environ["GROQ_API_KEY"], max_retries=4) as client:
        response = await client.chat.completions.create(
            model=model,
            reasoning_effort=effort,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": text},
            ],
            # strict: Groq makes the reply match the schema, so it always parses.
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": schema.model_json_schema(),
                },
            },
        )
    return schema.model_validate_json(response.choices[0].message.content)