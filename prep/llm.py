"""Ask gpt-oss on Groq for JSON that always matches a schema."""

import os

from groq import AsyncGroq, BadRequestError
from pydantic import BaseModel, ConfigDict

# Each Groq model has its own free limits, so the quick jobs and the planner
# use different models and don't eat into each other's tokens per minute.
FAST_MODEL = "openai/gpt-oss-20b"
SMART_MODEL = "openai/gpt-oss-120b"
TRIES = 3  # how many times to ask when a reply doesn't fit the schema


class Strict(BaseModel):
    """Base for every schema: no extra keys, which Groq's strict mode requires."""

    model_config = ConfigDict(extra="forbid")


async def ask_json(
    instructions: str, text: str, schema: type[BaseModel], model=FAST_MODEL, effort="low"
):
    """Send instructions plus text, and get back an instance of `schema`."""
    request = {
        "model": model,
        "reasoning_effort": effort,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": text},
        ],
        # strict: Groq makes the reply match the schema, and turns it down if it doesn't.
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__,
                "strict": True,
                "schema": schema.model_json_schema(),
            },
        },
    }
    # max_retries: if you hit a free per-minute limit, wait and try again.
    async with AsyncGroq(api_key=os.environ["GROQ_API_KEY"], max_retries=4) as client:
        for attempt in range(1, TRIES + 1):
            try:
                response = await client.chat.completions.create(**request)
                return schema.model_validate_json(response.choices[0].message.content)
            except BadRequestError as error:
                # Now and then the model writes JSON that doesn't fit the schema, and
                # Groq turns it down with json_validate_failed. Ask again when it does.
                if "json_validate_failed" not in str(error) or attempt == TRIES:
                    raise