from google import genai
client = genai.Client(api_key="AIzaSyAdLn4xTdXn0uxKS7F7zqmV_LJFBK0e7jk")
# Server-side state (recommended)
interaction1 = client.interactions.create(
    model="gemini-3-flash-preview",
    input="I have 2 cats in my house.",
)

client2 = genai.Client(api_key="AIzaSyAdLn4xTdXn0uxKS7F7zqmV_LJFBK0e7jk")
# Server-side state (recommended)
interaction2 = client.interactions.create(
   model="gemini-3-flash-preview",
   input="I have 2 dogs in my house.",
   previous_interaction_id=interaction1.id,
)

client3 = genai.Client(api_key="AIzaSyAdLn4xTdXn0uxKS7F7zqmV_LJFBK0e7jk")
# Server-side state (recommended)
interaction3 = client.interactions.create(
   model="gemini-3-flash-preview",
   input="how many pets do I have in my house?",
   previous_interaction_id=interaction2.id,
)

print(interaction2.output_text)