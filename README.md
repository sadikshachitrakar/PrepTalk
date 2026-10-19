# Interview Coach

A voice mock interviewer that reads a job description, your resume and the company, plans a tailored interview, asks the questions out loud, waits while you think, and saves every answer for feedback.

## Run it

1. Install uv, then put your keys in `.env` as `GROQ_API_KEY=...` and `GEMINI_API_KEY=...`
2. `uv run check_setup.py`
3. `uv run bot.py -t webrtc`, then open http://localhost:7860
4. Paste a job description, add your resume as a PDF, pick a mode and click Prepare my interview
5. Check the plan, then click Start the interview

Every tailored question quotes the line of the posting, resume or company research it came from, and code rejects any quote it can't find.

Built with Pipecat, Groq (Whisper and gpt-oss), Gemini with Google Search grounding, Kokoro and Smart Turn.