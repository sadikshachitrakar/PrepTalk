"""The models the tests run on, all on your free Groq key. The YAML files point to them."""

import asyncio
import os

from loguru import logger

from pipecat.classifiers.base_classifier import ClassifierError
from pipecat.classifiers.llm.classifier import LLMClassifier
from pipecat.services.groq.llm import GroqLLMService
from pipecat.services.groq.stt import GroqSTTService


def llm(config: dict) -> GroqLLMService:
    """gpt-oss on Groq, on the model the YAML file names. It plays the candidates."""
    return GroqLLMService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqLLMService.Settings(model=config["model"], reasoning_effort="low"),
    )


class PatientJudge(LLMClassifier):
    """Grades the interviewer one question at a time. When Groq's free per-minute
    limit is full, it waits and asks again instead of failing the test."""

    one_at_a_time = asyncio.Semaphore(1)

    async def _ask(self, state, questions):
        async with self.one_at_a_time:
            for wait in (15, 30, 45):
                try:
                    return await super()._ask(state, questions)
                except ClassifierError as error:
                    logger.warning(f"Judge waiting {wait} seconds to ask again: {error}")
                    await asyncio.sleep(wait)
            return await super()._ask(state, questions)


def judge(config: dict) -> PatientJudge:
    """The judge the YAML files name, on the model they give."""
    return PatientJudge(llm=llm(config), timeout=60)


def ears(config: dict) -> GroqSTTService:
    """Whisper, so the audio tests can hear what the interviewer says. It's a different
    Whisper model from the bot's, so it has its own free limits and doesn't use up the bot's."""
    return GroqSTTService(
        api_key=os.environ["GROQ_API_KEY"],
        settings=GroqSTTService.Settings(model="whisper-large-v3"),
    )