from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
import ollama
import os
import json
import re
import uuid
from datetime import datetime

app = Flask(__name__, static_folder='static/build', static_url_path='')
CORS(app, origins=["http://localhost:3000"])  # Enable CORS for development

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/build', exist_ok=True)

def get_available_models():
    """Get available models from Ollama and categorize them"""
    try:
        models_response = ollama.list()
        all_models = [model['model'] for model in models_response['models']]
        
        # Categorize models based on name patterns
        chat_models = []
        caption_models = []
        
        for model_name in all_models:
            model_lower = model_name.lower()
            # Image/vision models typically contain these keywords
            if any(keyword in model_lower for keyword in ['llava', 'vision', 'caption', 'clip', 'blip', 'vit', 'joycaption']):
                caption_models.append(model_name)
            else:
                chat_models.append(model_name)
        print(models_response)
        # Ensure we have at least one model in each category
        if not chat_models and all_models:
            chat_models = [all_models[0]]
        if not caption_models and all_models:
            caption_models = [all_models[0]]
            
        return chat_models, caption_models, all_models
        
    except Exception as e:
        print(f"Error getting models from Ollama: {e}")
        return ["wizard-vicuna-uncensored:7b"], ["aha2025/llama-joycaption-beta-one-hf-llava:Q4_K_M"], []

# Get available models on startup
chat_models, caption_models, all_models = get_available_models()
selected_chat_model = chat_models[0] if chat_models else "wizard-vicuna-uncensored:7b"
selected_image_model = caption_models[0] if caption_models else "aha2025/llama-joycaption-beta-one-hf-llava:Q4_K_M"

default_instruction = "Describe this image in detail, including what you see, the setting, objects, people, and any notable features."

def generate_caption(image_path, instruction=default_instruction):
    """Generate caption for image using Ollama"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"{image_path} not found")
    
    response = ollama.chat(
        model=selected_image_model,
        messages=[{
            "role": "user",
            "content": instruction,
            "images": [image_path]
        }]
    )
    return response["message"]["content"]

class CharacterChat:
    def __init__(self, character_file="characters.json"):
        self.character_file = character_file
        self.load_characters()
        self.messages = []
        self.current_character = None

    def load_characters(self):
        """Load characters from JSON file, create default if not exists"""
        if not os.path.exists(self.character_file):
            default_characters = {
                "assistant": {
                    "name": "Assistant",
                    "role": "Helpful AI Assistant",
                    "system_prompt": "You are a helpful AI assistant. Be friendly, informative, and helpful in all interactions.",
                    "image_caption_prompt": "Describe this image accurately and concisely"
                },
                "creative_writer": {
                    "name": "Creative Writer",
                    "role": "Creative Writing Specialist",
                    "system_prompt": "You are a creative writer with vivid imagination. Use descriptive language and engage in storytelling.",
                    "image_caption_prompt": "Describe this image with creative and poetic language"
                },
                "code_helper": {
                    "name": "Code Helper",
                    "role": "Programming Assistant",
                    "system_prompt": "You are a programming assistant. Help with coding questions, debug issues, and explain technical concepts.",
                    "image_caption_prompt": "Analyze this image for any technical or coding-related content"
                },
                "researcher": {
                    "name": "Researcher",
                    "role": "Research Assistant",
                    "system_prompt": "You are a research-focused assistant for academic work. Provide detailed, analytical responses.",
                    "image_caption_prompt": "Provide a detailed, analytical description of this image"
                }
            }
            with open(self.character_file, "w") as f:
                json.dump(default_characters, f, indent=2)
            
        with open(self.character_file, "r") as f:
            self.characters = json.load(f)

    def get_characters_list(self):
        """Return list of characters for dropdown"""
        return [{"name": char_data["name"], "key": key} for key, char_data in self.characters.items()]

    def set_character(self, character_key):
        """Set active character"""
        if character_key not in self.characters:
            raise ValueError(f"Character '{character_key}' not found")
        
        char_data = self.characters[character_key]
        self.current_character = char_data
        system_prompt = char_data["system_prompt"]
        
        if "user_profile" in char_data:
            system_prompt += f"\nImportant: The user should be treated as follows: {char_data['user_profile']}"
        
        self.messages = [{"role": "system", "content": system_prompt}]
        return char_data["name"]

    def process_image(self, image_path):
        """Process image and add to conversation"""
        instruction = self.current_character.get("image_caption_prompt", default_instruction)
        caption = generate_caption(image_path, instruction)
        
        self.messages.append({"role": "user", "content": f"user shows you this image: '{caption}'."})
        response = ollama.chat(model=selected_chat_model, messages=self.messages)
        answer = response["message"]["content"]
        self.messages.append({"role": "assistant", "content": answer})
        
        return caption, answer

    def ask(self, user_input):
        """Process user message and get AI response"""
        if re.match(r"^\*.*\*$", user_input.strip()):
            action = user_input.strip("*")
            formatted = f"(The user performs an action: {action})"
        else:
            formatted = user_input
        
        self.messages.append({"role": "user", "content": formatted})
        response = ollama.chat(model=selected_chat_model, messages=self.messages)
        answer = response["message"]["content"]
        self.messages.append({"role": "assistant", "content": answer})
        
        return answer

    def add_character(self, name, description, image_caption_prompt):
        """Add new character to JSON file"""
        character_key = name.lower().replace(" ", "_").replace("-", "_")
        
        if character_key in self.characters:
            raise ValueError(f"Character '{name}' already exists")
        
        new_character = {
            "name": name,
            "role": description or "Custom Character",
            "system_prompt": description or f"You are {name}. Engage naturally in conversation.",
            "image_caption_prompt": image_caption_prompt or "Describe this image"
        }
        
        self.characters[character_key] = new_character
        
        with open(self.character_file, "w") as f:
            json.dump(self.characters, f, indent=2)
        
        return character_key

    def reset_conversation(self):
        """Reset current conversation"""
        if self.current_character:
            system_prompt = self.current_character["system_prompt"]
            self.messages = [{"role": "system", "content": system_prompt}]
        else:
            self.messages = []

# Initialize global chat instance
chat = CharacterChat()

# ================================
# REACT APP SERVING ROUTES
# ================================

@app.route('/')
def serve_react_app():
    """Serve React app's index.html"""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except FileNotFoundError:
        return """
        <h1>React Build Not Found</h1>
        <p>Please build the React app first:</p>
        <ol>
            <li>cd frontend</li>
            <li>npm run build</li>
            <li>npm run copy-build</li>
        </ol>
        <p>Then restart the Flask server.</p>
        """, 404

@app.route('/<path:path>')
def serve_react_static(path):
    """Serve React static files or fallback to index.html for client-side routing"""
    try:
        return send_from_directory(app.static_folder, path)
    except FileNotFoundError:
        # For client-side routing, return index.html
        return send_from_directory(app.static_folder, 'index.html')

# ================================
# API ROUTES
# ================================

@app.route('/api/get_initial_data', methods=['GET'])
def get_initial_data():
    """Get initial data for React app"""
    characters_list = chat.get_characters_list()
    return jsonify({
        'success': True,
        'chat_models': chat_models,
        'caption_models': caption_models,
        'selected_chat_model': selected_chat_model,
        'selected_caption_model': selected_image_model,
        'characters': characters_list
    })

@app.route('/api/refresh_models', methods=['POST'])
def refresh_models():
    """Refresh the list of available models"""
    global chat_models, caption_models, all_models
    try:
        chat_models, caption_models, all_models = get_available_models()
        return jsonify({
            'success': True, 
            'message': 'Models refreshed successfully',
            'chat_models': chat_models,
            'caption_models': caption_models
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/send_message', methods=['POST'])
def send_message():
    """Handle message sending"""
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'error': 'Message cannot be empty'})
    
    if not chat.current_character:
        return jsonify({'success': False, 'error': 'No character selected'})
    
    try:
        response = chat.ask(message)
        return jsonify({
            'success': True, 
            'response': response,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False, 
            'error': str(e)
        })

@app.route('/api/select_chat_model', methods=['POST'])
def select_chat_model():
    global selected_chat_model
    data = request.get_json()
    model = data.get('model')
    
    if model in chat_models:
        selected_chat_model = model
        return jsonify({'success': True, 'message': f'Selected chat model: {model}'})
    else:
        return jsonify({'success': False, 'message': f'Model {model} not available'})

@app.route('/api/select_image_model', methods=['POST'])
def select_image_model():
    global selected_image_model
    data = request.get_json()
    model = data.get('model')
    
    if model in caption_models:
        selected_image_model = model
        return jsonify({'success': True, 'message': f'Selected image model: {model}'})
    else:
        return jsonify({'success': False, 'message': f'Model {model} not available'})

@app.route('/api/select_character', methods=['POST'])
def select_character():
    data = request.get_json()
    character = data.get('character')
    
    character_key = None
    for key, char_data in chat.characters.items():
        if char_data["name"] == character:
            character_key = key
            break
    
    if character_key:
        try:
            character_name = chat.set_character(character_key)
            return jsonify({'success': True, 'message': f'Selected character: {character}', 'character_name': character_name})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)})
    
    return jsonify({'success': False, 'message': 'Character not found'})

@app.route('/api/create_character', methods=['POST'])
def create_character():
    data = request.get_json()
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    image_caption_prompt = data.get('image_caption_prompt', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Character name is required'})
    
    try:
        character_key = chat.add_character(name, description, image_caption_prompt)
        return jsonify({
            'success': True, 
            'message': f'Character "{name}" created successfully',
            'character_name': name
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error creating character: {str(e)}'})

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    if file and chat.current_character:
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        try:
            file.save(filepath)
            caption, ai_response = chat.process_image(filepath)
            
            return jsonify({
                'success': True, 
                'message': 'Image processed successfully',
                'caption': caption,
                'response': ai_response,
                'filename': filename
            })
        except Exception as e:
            return jsonify({'error': str(e)})
    
    return jsonify({'error': 'No character selected or processing failed'})

@app.route('/api/reset_chat', methods=['POST'])
def reset_chat():
    chat.reset_conversation()
    return jsonify({'success': True, 'message': 'Chat reset successfully'})

@app.route('/api/toggle_dark_mode', methods=['POST'])
def toggle_dark_mode():
    return jsonify({'success': True, 'message': 'Dark mode toggled'})

if __name__ == '__main__':
    print("=== Ollama Chat UI ===")
    print(f"Available Chat Models ({len(chat_models)}): {chat_models}")
    print(f"Available Caption Models ({len(caption_models)}): {caption_models}")
    print(f"Selected Chat Model: {selected_chat_model}")
    print(f"Selected Image Model: {selected_image_model}")
    print("Starting Flask server on http://localhost:5000")
    print("React app will be served from http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
