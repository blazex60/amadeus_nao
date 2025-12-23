def get_amadeus_response(user_input):
    response = ollama.chat(model='llama3', messages=[
        {
            'role': 'system',
            'content': 'あなたは牧瀬紅莉栖の記憶を持つAI、Amadeusです。論理的かつ少し冷徹に相手の適性を判断してください。'
        },
        {'role': 'user', 'content': user_input},
    ])
    return response['message']['content']