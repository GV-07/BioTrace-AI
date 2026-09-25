import base64
from config import GEMINI_API_KEY
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

def stream_health_agent_response(query, chat_history, language, media_bytes=None, media_mime=None):
  api_key = GEMINI_API_KEY

  if not api_key or "YOUR_ACTUAL" in api_key:
    yield "⚠️ Please add your valid Gemini API key in `config.py`."
    return

  try:
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key
    )

    messages = [
        SystemMessage(
            content=(
                "You are BioTrace AI, an expert Indian Personal Health Assistant"
                " supporting patients with reliable medical information,"
                " medication safety, and wellness insights. Incorporate traditional"
                " Indian wellness/Ayurvedic context where appropriate, alongside"
                " modern standards. Always provide a disclaimer that this is not"
                " a substitute for professional medical advice. "
                f"CRITICAL INSTRUCTION: You MUST reply entirely in {language}."
            )
        )
    ]

    for msg in chat_history[:-1]:
      if msg["role"] == "user":
        messages.append(HumanMessage(content=msg["content"]))
      else:
        messages.append(AIMessage(content=msg["content"]))

    user_content = []
    if query and query.strip():
        user_content.append({"type": "text", "text": query})
    
    if media_bytes and media_mime:
        encoded_media = base64.b64encode(media_bytes).decode("utf-8")
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{media_mime};base64,{encoded_media}"}
        })

    if not user_content:
        user_content.append({"type": "text", "text": "Please analyze my input."})

    messages.append(HumanMessage(content=user_content))
    
    for chunk in llm.stream(messages):
        if isinstance(chunk.content, list):
            for block in chunk.content:
                if isinstance(block, dict) and "text" in block:
                    yield block["text"]
                elif isinstance(block, str):
                    yield block
        else:
            yield str(chunk.content)

  except Exception as e:
    yield f"⚠️ Gemini API Error: {str(e)}"