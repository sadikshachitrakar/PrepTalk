# Interview Coach

A voice mock interviewer that reads a job description, your resume and the company, plans a tailored interview, asks the questions out loud, waits while you think, then scores every answer with quotes, one fix and a stronger version.

## Run it

1. Install uv, then put your Groq key in `.env` as `GROQ_API_KEY=...`
2. `uv run check_setup.py`
3. `uv run bot.py -t webrtc`, then open http://localhost:7860
4. Paste a job description, add your resume as a PDF, pick a mode and click Prepare my interview
5. Check the plan, then click Start the interview
6. When the call ends, open http://localhost:7860/report

## How the feedback works

Each answer clip is transcribed again with word timings. Code measures length, pace, long pauses, fillers and hedges, and gpt-oss scores the content against a six-part rubric. Code checks every evidence quote against the transcript, and the stronger version may only use facts you said.

Built with Pipecat, Groq (Whisper and gpt-oss), Wikipedia, Kokoro, Smart Turn and SQLite.