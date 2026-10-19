"""The fixed parts of every interview: modes, follow-up rules and library questions."""

# Each mode is a list of question slots. Library slots use a fixed question;
# every other slot is written by the planner from the job, resume and company.
MODES = {
    "recruiter": {
        "name": "Recruiter screen",
        "minutes": 15,
        "slots": ["opener", "motivation", "resume", "start_date", "salary", "your_questions"],
        "follow_ups": True,
        "rules": "This is a recruiter screen: keep it warm and brisk, and skip deep technical detail.",
    },
    "behavioral": {
        "name": "Behavioral",
        "minutes": 30,
        "slots": ["opener"] + ["behavioral"] * 5 + ["your_questions"],
        "follow_ups": True,
        "rules": "This is a behavioral round: every main question asks for a real story.",
    },
    "technical": {
        "name": "Technical concepts",
        "minutes": 30,
        "slots": [
            "opener",
            "job_skill",
            "job_skill",
            "technical",
            "technical",
            "scenario",
            "your_questions",
        ],
        "follow_ups": True,
        "rules": "This is a technical round. For the scenario question, answer their clarifying questions in one sentence and let them lead.",
    },
    "full": {
        "name": "Full mix",
        "minutes": 45,
        "slots": [
            "opener",
            "motivation",
            "resume",
            "job_skill",
            "technical",
            "scenario",
            "behavioral",
            "behavioral",
            "situational",
            "company",
            "your_questions",
        ],
        "follow_ups": True,
        "rules": "This is a full dress rehearsal that mixes every kind of question.",
    },
    "screener": {
        "name": "Timed screener drill",
        "minutes": 12,
        "slots": ["opener", "motivation", "job_skill", "behavioral", "situational", "start_date"],
        "follow_ups": False,
        "rules": "This is a timed screener drill. Skip small talk: after your one-sentence greeting, say each answer has a two-minute limit. Don't answer questions about the company.",
    },
}

FOLLOW_UP_RULES = {
    "friendly": "Don't ask follow-ups. If the candidate is stuck or asks for help, give one short hint based on the notes, then let them answer.",
    "standard": 'Ask at most one follow-up per question, and only when the answer has a gap: no result, only "we" with no part of their own, or nothing specific. Use a planned follow-up when one fits. If the answer is complete, move on.',
    "tough": "Ask up to two follow-ups per question. Press for numbers, their own part and the trade-offs they weighed. Stay polite but skeptical: when a claim sounds big, ask how they measured it. If the answer is complete, move on.",
}

# Kokoro voices: the first letter is the accent (a = American, b = British).
VOICES = {
    "af_heart": "Heart (American, female)",
    "am_michael": "Michael (American, male)",
    "bf_emma": "Emma (British, female)",
    "bm_george": "George (British, male)",
}

# Questions every interview can use as they are.
LIBRARY = {
    "opener": {
        "question": "Tell me about yourself, and what brings you to this role.",
        "strong_answer_covers": [
            "a 60 to 90 second story",
            "two or three highlights that fit this job",
            "an ending that explains why this role",
        ],
        "follow_ups": ["What part of your background fits this role best?"],
    },
    "start_date": {
        "question": "If you got an offer, when could you start?",
        "strong_answer_covers": ["a clear date or notice period"],
        "follow_ups": [],
    },
    "salary": {
        "question": "What are your salary expectations for this role?",
        "strong_answer_covers": [
            "a researched range rather than one number",
            "openness to the whole package",
        ],
        "follow_ups": ["How did you arrive at that range?"],
    },
    "your_questions": {
        "question": "Those are all my questions. What questions do you have for me?",
        "strong_answer_covers": [
            "one or two specific questions the company website doesn't already answer"
        ],
        "follow_ups": [],
    },
}

# Used when the planner's question for a slot can't show where it came from.
FALLBACKS = {
    "motivation": {
        "question": "Why do you want this role, and why now?",
        "strong_answer_covers": ["something specific about the role", "how it fits your next step"],
        "follow_ups": ["What would you want to learn in your first six months?"],
    },
    "resume": {
        "question": "Walk me through the project on your resume you're proudest of. Which decisions were yours?",
        "strong_answer_covers": ["your own role", "a decision you made", "a result with a number"],
        "follow_ups": ["What did you do yourself?", "How did you measure the result?"],
    },
    "job_skill": {
        "question": "Which skill from this job description is your strongest, and where have you used it?",
        "strong_answer_covers": ["one skill", "a real example", "the outcome"],
        "follow_ups": ["Can you give me a specific example?"],
    },
    "technical": {
        "question": "Pick a technical idea from your recent work and explain it the way you would to a product manager.",
        "strong_answer_covers": ["plain language", "an example", "why it matters"],
        "follow_ups": ["How would you know it's working?"],
    },
    "scenario": {
        "question": "Suppose you joined and were asked to build something with unclear requirements. How would you start?",
        "strong_answer_covers": [
            "clarifying questions",
            "a small first version",
            "how you'd test it",
        ],
        "follow_ups": ["What would you ask first?"],
    },
    "behavioral": {
        "question": "Tell me about a time something you were responsible for went wrong. What did you do?",
        "strong_answer_covers": [
            "the situation",
            "your own actions",
            "the result",
            "what you learned",
        ],
        "follow_ups": ["What did you do yourself?", "What would you do differently?"],
    },
    "situational": {
        "question": "If two urgent tasks landed on the same day, how would you decide what to do first?",
        "strong_answer_covers": ["a clear way to prioritize", "who you'd tell", "the trade-off"],
        "follow_ups": ["Who would you check with?"],
    },
    "company": {
        "question": "What do you know about what we do, and what would you want to work on here?",
        "strong_answer_covers": [
            "a specific product or mission detail",
            "a link to your own skills",
        ],
        "follow_ups": ["What would you improve first?"],
    },
}