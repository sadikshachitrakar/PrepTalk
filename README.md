# Interview Coach

A voice mock interviewer that reads a job description, your resume and the company, plans a tailored interview, asks the questions out loud, waits while you think, then scores every answer with quotes, one fix and a stronger version.

## How it works

1. **Prep.** It reads the job posting and your resume PDF (with your email and phone number removed), and looks the company up on Wikipedia. Then it writes questions for the mode you pick. Every tailored question must quote, word for word, the line of the posting, resume or company facts it came from. If it can't, a standard question takes its place.
2. **Interview.** A voice call in the browser: Whisper hears you, gpt-oss runs the interview, and Kokoro speaks on your laptop. It asks one question at a time, asks a follow-up when an answer has no result or only says "we", and waits while you think.
3. **Feedback.** When the call ends, each answer is transcribed again with word timings and scored. The report and your progress over time are at `/report` and `/history`.

## Run it

1. Install uv, then put your Groq key in `.env` as `GROQ_API_KEY=...`
2. `uv run check_setup.py`
3. `uv run bot.py -t webrtc`, then open http://localhost:7860
4. Paste a job description, add your resume as a PDF, pick a mode and click Prepare my interview
5. Check the plan, then click Start the interview
6. When the call ends, open http://localhost:7860/report

Use headphones, so the interviewer doesn't hear itself.

| Mode | Minutes | What it covers |
|---|---|---|
| Recruiter screen | 15 | Background, motivation, one resume project, start date, salary |
| Behavioral | 30 | Five "tell me about a time" stories |
| Technical concepts | 30 | Job skills, concepts, a scenario |
| Full mix | 45 | A bit of everything |
| Timed screener drill | 12 | No follow-ups, two minutes an answer |

## How the interviewer stays on script

An LLM can't be trusted to run an interview on its own, so the code checks it.

- **It waits while you think.** Smart Turn listens for an unfinished sentence. The LLM also marks whether your answer is finished (●) or not (◐ or ○), and if it isn't, the interviewer waits instead of cutting in.
- **One turn at a time.** Sometimes the model finishes its question and then carries on into the next turn, even answering for you. `OneTurnPerReply` cuts the reply at that point, so it's never spoken or saved.
- **It stops when time is up.** Telling the model "time is up" didn't work: it asked another question anyway. So `TimeKeeper` does it in code: after your current answer, the interviewer's next reply is swapped for a goodbye and the call ends.
- **The goodbye can't be cut off.** Once the interview is ending, your microphone is muted.

These came from measuring, not guessing. I replayed the exact model calls behind the failures, many times each:

| Problem | Before | After |
|---|---|---|
| Ended the interview after the first answer | 3 in 10 (gpt-oss-20b) | 0 in 28 (gpt-oss-120b) |
| Ran on into the next turn | 6 in 8 (120b, low reasoning) | 0 in 8 (120b, medium reasoning) |
| Asked another question when time was up | up to 8 in 8 | handled in code |

So the interviewer runs on gpt-oss-120b at medium reasoning effort, which costs about 0.4 seconds a reply.

## How the feedback works

Each answer clip is transcribed again with word timings. Code measures length, pace, long pauses, fillers and hedges. gpt-oss scores the content against a six-part rubric: answers the question, structure, specificity, ownership, result and reflection, and role fit. Code checks every evidence quote against the transcript and drops any that isn't there. The stronger version may only use facts you said: any number you never said becomes "[add the number]".

## Tests

```
uv run pipecat eval suite tests/manifest.yaml   # the interviewer, scripted and with simulated candidates
uv run python -m tests.check_feedback           # does the scorer rank a strong answer above a weak one?
uv run python -m tests.make_clips               # make answer clips with known pauses
uv run python -m tests.check_delivery           # are the pause and pace numbers right?
```

- `tests/interviewer.yaml`: scripted checks, such as one question at a time, asking for the result, no feedback during the interview, and ending after the last question.
- `tests/candidates.yaml`: an LLM plays a rambler, a one-word answerer, a "we" storyteller, a clarifier and a drifter. A judge reads every reply.
- `tests/time_up.yaml`: with a 30-second limit, the call must end after the next answer. It isn't in the manifest yet: add `time_up` to the `short_on_time` entry's scenarios to run it.
- `tests/pauses.yaml` (made by `make_clips`): the interviewer must not cut in during a thinking pause.

## Free tier limits

Everything runs on Groq's free tier, which has limits:

- gpt-oss-120b allows 8,000 tokens a minute and 200,000 a day. The interviewer, the planner, the scorer and the test judge all use it, so a full test run eats into the same daily budget as your interviews.
- Each interviewer reply resends the whole conversation, so replies get bigger as the interview goes on. Shorter modes (Recruiter screen, Timed screener) stay well inside the limits; Full mix can hit the per-minute limit near the end.
- If you run out, the interviewer goes quiet. Groq's paid Dev tier lifts the limits.

## Project layout

```
bot.py            the voice pipeline and web server
interview.py      the interviewer prompt, end_interview, OneTurnPerReply, TimeKeeper
recorder.py       saves answer clips, the transcript and response times to sessions/
prep/             job, resume and company research, and the question planner
feedback/         transcription, delivery, scoring, the report and history
prompts/          the interviewer and scorer prompts
pages/            the setup, plan, report and history pages
tests/            evals and checks
```

Built with Pipecat, Groq (Whisper and gpt-oss), Wikipedia, Kokoro, Smart Turn and SQLite.
