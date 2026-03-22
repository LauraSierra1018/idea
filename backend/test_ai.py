from openai import OpenAI
import json

client = OpenAI()

# prompt
system_prompt = """
Eres un agente que diseña planes de entrenamiento simples.

Debes:
- respetar el tiempo por sesión
- generar un plan semanal
- explicar brevemente cada sesión

Responde SOLO en formato JSON.
"""

# perfil de usuario
user_profile = {
    "edad": 45,
    "nivel": "principiante",
    "objetivo": "salud",
    "tiempo_por_sesion": 30,
    "dias_por_semana": 3
}

# tarea
task = f"""
Usando el siguiente perfil de usuario:

{json.dumps(user_profile)}

Genera un plan semanal de entrenamiento.
"""

# llamada a la API de OpenAI
response = client.responses.create(
    model="gpt-4.1-mini",
    input=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task}
    ]
)

print(response.output_text)