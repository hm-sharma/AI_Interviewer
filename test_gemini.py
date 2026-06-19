import google.generativeai as genai

API_KEY = "AIzaSyCrgfzH5r_SmhQsfCbkrJxqFExkY4lWW0Q"
MODEL_NAME = "models/gemini-3.5-flash"
EMBEDDING_MODEL = "models/gemini-embedding-001"

print(f"Configuring Gemini with API key: {API_KEY[:6]}...{API_KEY[-6:]}")
genai.configure(api_key=API_KEY)

try:
    print(f"1. Testing Generation with {MODEL_NAME}...")
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content("Hello! Are you online and working?")
    print("Response text:", response.text.strip())
    print("Generation: SUCCESS")
except Exception as e:
    print(f"Generation: FAILED. Error: {e}")

try:
    print(f"2. Testing Embedding with {EMBEDDING_MODEL}...")
    emb = genai.embed_content(
        model=EMBEDDING_MODEL,
        content="Testing embedding generation",
        task_type="retrieval_document"
    )
    print(f"Embedding length: {len(emb['embedding'])}")
    print("Embedding: SUCCESS")
except Exception as e:
    print(f"Embedding: FAILED. Error: {e}")
