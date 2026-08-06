SYSTEM_PROMPT = (
    "You are a friendly voice assistant. Your replies are spoken aloud, so "
    "keep them short, clear, and conversational. Answer in one or two natural "
    "sentences. Do not use markdown, bullet points, code blocks, or emoji."
)


def build_messages(transcript, history=None):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": transcript})
    return messages
