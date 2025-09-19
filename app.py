from flask import Flask, render_template, request, jsonify, send_from_directory, session
from werkzeug.utils import secure_filename
from flask_cors import CORS
from PIL import Image
import ollama
import os
import json
import re
import uuid
from datetime import datetime
import secrets
import subprocess
import threading
import queue
import time
import requests
import sys
import socket

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "templates"),
            static_folder=os.path.join(BASE_DIR, "static"))

#app = Flask(__name__, static_folder='static/build', static_url_path='')
CORS(app, supports_credentials=True)  # Enable credentials for sessions

# Configure session management
app.config['SECRET_KEY'] = secrets.token_hex(16)  # Generate random secret key
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create directories if they don't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/build', exist_ok=True)

# Global session store - each session gets its own CharacterChat instance
chat_sessions = {}

# Model download tracking
download_progress = {}  # Track download progress per session
download_threads = {}  # Track active downloads

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
        
        # Ensure we have at least one model in each category
        if not chat_models and all_models:
            chat_models = [all_models[0]]
        if not caption_models and all_models:
            caption_models = [all_models[0]]
            
        return chat_models, caption_models, all_models
        
    except Exception as e:
        print(f"Error getting models from Ollama: {e}")
        return ["wizard-vicuna-uncensored:7b"], ["aha2025/llama-joycaption-beta-one-hf-llava:Q4_K_M"], []

def get_local_models():
    """Get list of locally installed models using ollama list command"""
    try:
        result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return []
        
        lines = result.stdout.strip().split('\n')
        models = []
        
        # Skip header line
        for line in lines[1:]:
            if line.strip():
                parts = line.split()
                if len(parts) >= 4:
                    model_info = {
                        'name': parts[0],
                        'id': parts[1] if len(parts) > 1 else 'unknown',
                        'size': parts[2] if len(parts) > 2 else 'unknown',
                        'modified': ' '.join(parts[3:]) if len(parts) > 3 else 'unknown'
                    }
                    models.append(model_info)
        
        return models
    except Exception as e:
        print(f"Error getting local models: {e}")
        return []

def delete_ollama_model(model_name):
    """Delete a model using ollama rm command"""
    try:
        result = subprocess.run(['ollama', 'rm', model_name], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True, f"Successfully deleted {model_name}"
        else:
            error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            return False, f"Failed to delete {model_name}: {error_msg}"
    except subprocess.TimeoutExpired:
        return False, f"Timeout while deleting {model_name}"
    except Exception as e:
        return False, f"Error deleting {model_name}: {str(e)}"

# Get available models on startup
chat_models, caption_models, all_models = get_available_models()
selected_chat_model = chat_models[0] if chat_models else "wizard-vicuna-uncensored:7b"
selected_image_model = caption_models[0] if caption_models else "aha2025/llama-joycaption-beta-one-hf-llava:Q4_K_M"

default_instruction = "Describe this image in detail, including what you see, the setting, objects, people, and any notable features."

def generate_caption(image_path, instruction=default_instruction, model=None):
    """Generate caption for image using Ollama"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"{image_path} not found")
    
    caption_model = model or selected_image_model
    response = ollama.chat(
        model=caption_model,
        messages=[{
            "role": "user",
            "content": instruction,
            "images": [image_path]
        }]
    )
    return response["message"]["content"]

def execute_ollama_pull(model_name, session_id, progress_queue):
    """Execute ollama pull command with improved progress tracking"""
    try:
        print(f"Starting download of {model_name} for session {session_id[:8]}...")
        
        # Initialize progress
        download_progress[session_id] = {
            'status': 'downloading',
            'model': model_name,
            'progress': 0,
            'message': f'Initializing download of {model_name}...',
            'started_at': time.time()
        }
        
        # Check if ollama is available
        try:
            subprocess.run(['ollama', '--version'], check=True, capture_output=True, text=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            download_progress[session_id].update({
                'status': 'error',
                'progress': 0,
                'message': 'Ollama is not installed or not available in PATH'
            })
            return

        # Execute ollama pull command with real-time output
        cmd = ['ollama', 'pull', model_name]
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Redirect stderr to stdout
            text=True,
            bufsize=1,  # Line buffered
            universal_newlines=True,
            env=os.environ.copy()  # Use current environment
        )
        
        download_progress[session_id].update({
            'progress': 5,
            'message': f'Connecting to download {model_name}...'
        })
        
        # Read output line by line in real-time
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            
            if output:
                line = output.strip()
                print(f"Ollama output: {line}")  # Debug output
                
                # Parse progress from different output patterns
                progress_updated = False
                
                # Pattern 1: "pulling abc123... 45.2MB/100.5MB"
                size_match = re.search(r'pulling\s+\w+\.\.\.\s+([\d.]+)\w+/([\d.]+)\w+', line)
                if size_match:
                    current = float(size_match.group(1))
                    total = float(size_match.group(2))
                    if total > 0:
                        percent = int((current / total) * 100)
                        download_progress[session_id].update({
                            'progress': min(percent, 95),
                            'message': f'Downloading {model_name}... {current:.1f}/{total:.1f}MB'
                        })
                        progress_updated = True

                # Pattern 2: Direct percentage "45%"
                if not progress_updated:
                    percent_match = re.search(r'(\d+)%', line)
                    if percent_match:
                        percent = int(percent_match.group(1))
                        download_progress[session_id].update({
                            'progress': min(percent, 95),
                            'message': f'Downloading {model_name}... {percent}%'
                        })
                        progress_updated = True

                # Pattern 3: Status messages
                if not progress_updated:
                    if 'pulling manifest' in line.lower():
                        download_progress[session_id].update({
                            'progress': 10,
                            'message': f'Fetching {model_name} manifest...'
                        })
                    elif 'pulling' in line.lower() and 'config' in line.lower():
                        download_progress[session_id].update({
                            'progress': 15,
                            'message': f'Downloading {model_name} configuration...'
                        })
                    elif 'verifying' in line.lower():
                        download_progress[session_id].update({
                            'progress': 90,
                            'message': f'Verifying {model_name}...'
                        })
                    elif 'success' in line.lower() or 'complete' in line.lower():
                        download_progress[session_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'message': f'Successfully downloaded {model_name}!'
                        })

        # Check final status
        return_code = process.poll()
        if return_code == 0:
            download_progress[session_id].update({
                'status': 'completed',
                'progress': 100,
                'message': f'Successfully downloaded {model_name}!'
            })
            print(f"✅ Successfully downloaded {model_name}")
            
            # Refresh global model lists
            global chat_models, caption_models, all_models
            try:
                chat_models, caption_models, all_models = get_available_models()
                print(f"📋 Updated model lists: {len(all_models)} total models")
            except:
                pass
                
        else:
            # Get any error output
            try:
                error_output = process.stdout.read() if process.stdout else "Unknown error"
            except:
                error_output = "Failed to read error output"
            
            download_progress[session_id].update({
                'status': 'error',
                'progress': 0,
                'message': f'Failed to download {model_name}: {error_output[:200]}'
            })
            print(f"❌ Failed to download {model_name}: {error_output}")
            
    except Exception as e:
        error_msg = str(e)
        download_progress[session_id].update({
            'status': 'error',
            'progress': 0,
            'message': f'Error downloading {model_name}: {error_msg}'
        })
        print(f"🚨 Exception during download: {e}")
    finally:
        # Clean up thread tracking
        if session_id in download_threads:
            del download_threads[session_id]

def download_model_via_api(model_name, session_id):
    """Alternative method using Ollama's REST API"""
    try:
        download_progress[session_id] = {
            'status': 'downloading',
            'model': model_name,
            'progress': 0,
            'message': f'Starting API download of {model_name}...',
            'started_at': time.time()
        }
        
        # Use Ollama's REST API
        url = 'http://localhost:11434/api/pull'
        payload = {'name': model_name, 'stream': True}
        
        response = requests.post(url, json=payload, stream=True, timeout=30)
        
        if response.status_code != 200:
            download_progress[session_id].update({
                'status': 'error',
                'message': f'API Error: {response.status_code}'
            })
            return
            
        for line in response.iter_lines():
            if line:
                try:
                    data = json.loads(line.decode('utf-8'))
                    
                    if 'status' in data:
                        status = data['status']
                        if 'completed' in data and 'total' in data and data['total'] > 0:
                            progress = int((data['completed'] / data['total']) * 100)
                            download_progress[session_id].update({
                                'progress': progress,
                                'message': f'{status}: {progress}%'
                            })
                        else:
                            download_progress[session_id].update({
                                'message': status
                            })
                            
                    if data.get('status') == 'success':
                        download_progress[session_id].update({
                            'status': 'completed',
                            'progress': 100,
                            'message': f'Successfully downloaded {model_name}!'
                        })
                        break
                        
                except json.JSONDecodeError:
                    continue
                    
    except requests.exceptions.ConnectionError:
        download_progress[session_id].update({
            'status': 'error',
            'message': 'Cannot connect to Ollama server. Is it running?'
        })
    except Exception as e:
        download_progress[session_id].update({
            'status': 'error',
            'message': f'API Error: {str(e)}'
        })
    finally:
        # Clean up thread tracking
        if session_id in download_threads:
            del download_threads[session_id]

class CharacterChat:
    def __init__(self, character_file="characters.json"):
        self.character_file = character_file
        self.load_characters()
        self.messages = []
        self.current_character = None
        self.selected_chat_model = selected_chat_model
        self.selected_image_model = selected_image_model

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
        caption = generate_caption(image_path, instruction, self.selected_image_model)
        
        self.messages.append({"role": "user", "content": f"user shows you this image: '{caption}'."})
        response = ollama.chat(model=self.selected_chat_model, messages=self.messages)
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
        response = ollama.chat(model=self.selected_chat_model, messages=self.messages)
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

def get_session_id():
    """Get or create session ID"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
        session.permanent = True  # Make session persistent
    return session['session_id']

def get_chat_session():
    """Get or create chat session for current user"""
    session_id = get_session_id()
    
    if session_id not in chat_sessions:
        chat_sessions[session_id] = CharacterChat()
        print(f"Created new chat session: {session_id[:8]}... (Total sessions: {len(chat_sessions)})")
    
    return chat_sessions[session_id]

def cleanup_old_sessions():
    """Clean up old inactive sessions (optional, for memory management)"""
    # This could be enhanced with timestamp tracking and periodic cleanup
    if len(chat_sessions) > 100:  # Arbitrary limit
        oldest_sessions = list(chat_sessions.keys())[:50]
        for session_id in oldest_sessions:
            del chat_sessions[session_id]
        print(f"Cleaned up {len(oldest_sessions)} old sessions")

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
            <li>npm run build-and-copy</li>
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
    chat = get_chat_session()
    characters_list = chat.get_characters_list()
    session_id = get_session_id()
    
    return jsonify({
        'success': True,
        'chat_models': chat_models,
        'caption_models': caption_models,
        'selected_chat_model': chat.selected_chat_model,
        'selected_caption_model': chat.selected_image_model,
        'characters': characters_list,
        'session_id': session_id,
        'active_sessions': len(chat_sessions)
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
    chat = get_chat_session()
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'success': False, 'error': 'Message cannot be empty'})
    
    if not chat.current_character:
        return jsonify({'success': False, 'error': 'No character selected'})
    
    try:
        response = chat.ask(message)
        cleanup_old_sessions()  # Optional cleanup
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
    """Select chat model for current session"""
    chat = get_chat_session()
    data = request.get_json()
    model = data.get('model')
    
    if model in chat_models:
        chat.selected_chat_model = model
        return jsonify({'success': True, 'message': f'Selected chat model: {model}'})
    else:
        return jsonify({'success': False, 'message': f'Model {model} not available'})

@app.route('/api/select_image_model', methods=['POST'])
def select_image_model():
    """Select image model for current session"""
    chat = get_chat_session()
    data = request.get_json()
    model = data.get('model')
    
    if model in caption_models:
        chat.selected_image_model = model
        return jsonify({'success': True, 'message': f'Selected image model: {model}'})
    else:
        return jsonify({'success': False, 'message': f'Model {model} not available'})

@app.route('/api/select_character', methods=['POST'])
def select_character():
    """Select character for current session"""
    chat = get_chat_session()
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
    """Create or update character for current session"""
    chat = get_chat_session()
    data = request.get_json()
    
    key = data.get('key', '').strip()  # If provided, we're editing
    name = data.get('name', '').strip()
    description = data.get('description', '').strip()
    image_caption_prompt = data.get('image_caption_prompt', '').strip()
    
    if not name:
        return jsonify({'success': False, 'message': 'Character name is required'})

    try:
        if key:
            # Edit existing character
            if key not in chat.characters:
                return jsonify({'success': False, 'message': 'Character not found'})
            
            chat.characters[key].update({
                'name': name,
                'role': description or 'Custom Character',
                'system_prompt': description or f'You are {name}. Engage naturally in conversation.',
                'image_caption_prompt': image_caption_prompt or 'Describe this image'
            })
            message = f'Character "{name}" updated successfully'
        else:
            # Create new character
            character_key = chat.add_character(name, description, image_caption_prompt)
            message = f'Character "{name}" created successfully'
        
        # Reload characters for all sessions
        for session_chat in chat_sessions.values():
            session_chat.load_characters()
        
        return jsonify({
            'success': True, 
            'message': message,
            'character_name': name
        })
    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saving character: {str(e)}'})

@app.route('/api/upload_image', methods=['POST'])
def upload_image():
    """Upload and process image for current session"""
    chat = get_chat_session()
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'})
    
    if file and chat.current_character:
        filename = secure_filename(file.filename)
        session_id = get_session_id()
        unique_filename = f"{session_id[:8]}_{uuid.uuid4()}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        
        try:
            file.save(filepath)
            caption, ai_response = chat.process_image(filepath)
            
            # Clean up uploaded file after processing (optional)
            try:
                os.remove(filepath)
            except:
                pass
            
            return jsonify({
                'success': True, 
                'message': 'Image processed successfully',
                'caption': caption,
                'response': ai_response,
                'filename': filename
            })
        except Exception as e:
            # Clean up file on error
            try:
                os.remove(filepath)
            except:
                pass
            return jsonify({'error': str(e)})
    
    return jsonify({'error': 'No character selected or processing failed'})

@app.route('/api/reset_chat', methods=['POST'])
def reset_chat():
    """Reset chat for current session"""
    chat = get_chat_session()
    chat.reset_conversation()
    return jsonify({'success': True, 'message': 'Chat reset successfully'})

@app.route('/api/get_session_info', methods=['GET'])
def get_session_info():
    """Get current session information"""
    session_id = get_session_id()
    return jsonify({
        'session_id': session_id,
        'active_sessions': len(chat_sessions),
        'session_short_id': session_id[:8] + '...'
    })

@app.route('/api/toggle_dark_mode', methods=['POST'])
def toggle_dark_mode():
    """Toggle dark mode (client-side only, no server state needed)"""
    return jsonify({'success': True, 'message': 'Dark mode toggled'})

# ================================
# CHARACTER MANAGEMENT API ROUTES
# ================================

@app.route('/api/characters', methods=['GET'])
def api_get_characters():
    """Get full list of characters with all details"""
    chat = get_chat_session()
    chat.load_characters()
    characters = []
    for key, char in chat.characters.items():
        characters.append({
            'key': key,
            'name': char.get('name', ''),
            'role': char.get('role', ''),
            'system_prompt': char.get('system_prompt', ''),
            'image_caption_prompt': char.get('image_caption_prompt', ''),
            'user_profile': char.get('user_profile', '')
        })
    return jsonify({'success': True, 'characters': characters})

@app.route('/api/characters/edit', methods=['POST'])
def api_edit_character():
    """Edit an existing character"""
    data = request.get_json()
    key = data.get('key', '').strip()
    name = data.get('name', '').strip()
    role = data.get('role', '').strip()
    system_prompt = data.get('system_prompt', '').strip()
    image_caption_prompt = data.get('image_caption_prompt', '').strip()
    user_profile = data.get('user_profile', '').strip()

    if not key or not name:
        return jsonify({'success': False, 'message': 'Character key and name are required'})

    chat = get_chat_session()
    chat.load_characters()

    if key not in chat.characters:
        return jsonify({'success': False, 'message': f'Character "{key}" not found'})

    # Update character
    chat.characters[key].update({
        'name': name,
        'role': role or 'Custom Character',
        'system_prompt': system_prompt or f'You are {name}. Engage naturally in conversation.',
        'image_caption_prompt': image_caption_prompt or 'Describe this image',
        'user_profile': user_profile
    })

    try:
        with open(chat.character_file, 'w') as f:
            json.dump(chat.characters, f, indent=2)
        
        # Refresh characters for all sessions
        for session_chat in chat_sessions.values():
            session_chat.load_characters()
        
        return jsonify({
            'success': True, 
            'message': f'Character "{name}" updated successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to update character: {str(e)}'})

@app.route('/api/characters/delete', methods=['POST'])
def api_delete_character():
    """Delete a character"""
    data = request.get_json()
    key = data.get('key', '').strip()

    if not key:
        return jsonify({'success': False, 'message': 'Character key is required'})

    # Prevent deletion of default characters
    default_characters = ['assistant', 'creative_writer', 'code_helper', 'researcher']
    if key in default_characters:
        return jsonify({'success': False, 'message': 'Cannot delete default characters'})

    chat = get_chat_session()
    chat.load_characters()

    if key not in chat.characters:
        return jsonify({'success': False, 'message': f'Character "{key}" not found'})

    character_name = chat.characters[key].get('name', key)
    
    try:
        del chat.characters[key]
        
        with open(chat.character_file, 'w') as f:
            json.dump(chat.characters, f, indent=2)
        
        # Refresh characters for all sessions
        for session_chat in chat_sessions.values():
            session_chat.load_characters()
        
        return jsonify({
            'success': True, 
            'message': f'Character "{character_name}" deleted successfully'
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to delete character: {str(e)}'})

# ================================
# MODEL MANAGEMENT API ROUTES
# ================================

@app.route('/api/models/list', methods=['GET'])
def api_list_models():
    """Get list of locally installed models"""
    try:
        models = get_local_models()
        return jsonify({
            'success': True,
            'models': models,
            'count': len(models)
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error listing models: {str(e)}',
            'models': []
        })

@app.route('/api/models/delete', methods=['POST'])
def api_delete_model():
    """Delete a locally installed model"""
    data = request.get_json()
    model_name = data.get('model_name', '').strip()
    
    if not model_name:
        return jsonify({'success': False, 'message': 'Model name is required'})
    
    try:
        success, message = delete_ollama_model(model_name)
        
        if success:
            # Refresh global model lists after deletion
            global chat_models, caption_models, all_models
            chat_models, caption_models, all_models = get_available_models()
        
        return jsonify({
            'success': success,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error deleting model: {str(e)}'
        })

@app.route('/api/models/stats', methods=['GET'])
def api_model_stats():
    """Get model statistics and system info"""
    try:
        models = get_local_models()
        total_models = len(models)
        
        # Calculate total size (rough estimate)
        total_size = 0
        for model in models:
            try:
                size_str = model.get('size', '0B')
                if 'GB' in size_str:
                    total_size += float(size_str.replace('GB', '').strip())
                elif 'MB' in size_str:
                    total_size += float(size_str.replace('MB', '').strip()) / 1024
            except:
                pass
        
        # Check if ollama is running
        try:
            result = subprocess.run(['ollama', 'ps'], capture_output=True, text=True, timeout=5)
            running_models = []
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:  # Skip header
                    if line.strip():
                        parts = line.split()
                        if parts:
                            running_models.append(parts[0])
        except:
            running_models = []
        
        return jsonify({
            'success': True,
            'stats': {
                'total_models': total_models,
                'total_size_gb': round(total_size, 2),
                'running_models': running_models,
                'running_count': len(running_models)
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting stats: {str(e)}'
        })

@app.route('/api/test_ollama', methods=['GET'])
def test_ollama():
    """Test ollama installation and basic functionality"""
    try:
        # Test 1: Check if ollama is installed
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True, timeout=5)
        version_info = result.stdout.strip() if result.returncode == 0 else "Not available"
        
        # Test 2: Check if ollama server is running
        try:
            list_result = subprocess.run(['ollama', 'list'], capture_output=True, text=True, timeout=10)
            server_running = list_result.returncode == 0
            current_models = list_result.stdout if server_running else "Server not running"
        except subprocess.TimeoutExpired:
            server_running = False
            current_models = "Timeout - server may be starting"
        
        return jsonify({
            'success': True,
            'ollama_version': version_info,
            'server_running': server_running,
            'current_models': current_models,
            'system_info': {
                'python_version': f"{sys.version_info.major}.{sys.version_info.minor}",
                'platform': os.name
            }
        })
        
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Ollama is not installed or not in PATH',
            'suggestion': 'Please install Ollama from https://ollama.com/download'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error testing Ollama: {str(e)}'
        })

@app.route('/api/download_model', methods=['POST'])
def download_model():
    """Start downloading a model with improved error handling"""
    session_id = get_session_id()
    data = request.get_json()
    model_name = data.get('model_name', '').strip()
    
    if not model_name:
        return jsonify({'success': False, 'message': 'Model name is required'})
    
    # Check if already downloading
    if session_id in download_threads and download_threads[session_id].is_alive():
        return jsonify({'success': False, 'message': 'A download is already in progress'})
    
    # Enhanced model name validation
    if not re.match(r'^[a-zA-Z0-9._:-]+$', model_name):
        return jsonify({'success': False, 'message': 'Invalid model name format. Use only letters, numbers, dots, hyphens, and colons.'})
    
    # Test ollama availability
    try:
        result = subprocess.run(['ollama', '--version'], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return jsonify({'success': False, 'message': 'Ollama is not working properly'})
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        return jsonify({'success': False, 'message': 'Ollama is not installed or not available. Please install Ollama first.'})
    
    try:
        # Start download in background thread
        progress_queue = queue.Queue()
        
        # Try CLI method first, fallback to API
        download_method = data.get('method', 'cli')  # Default to CLI
        if download_method == 'api':
            download_thread = threading.Thread(
                target=download_model_via_api,
                args=(model_name, session_id),
                daemon=True
            )
        else:
            download_thread = threading.Thread(
                target=execute_ollama_pull,
                args=(model_name, session_id, progress_queue),
                daemon=True
            )
        
        download_thread.start()
        
        # Track the thread
        download_threads[session_id] = download_thread
        
        print(f"🚀 Started download thread for {model_name} using {download_method} method")
        
        return jsonify({
            'success': True,
            'message': f'Started downloading {model_name}',
            'model_name': model_name,
            'method': download_method
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to start download: {str(e)}'})

@app.route('/api/download_progress', methods=['GET'])
def get_download_progress():
    """Get download progress for current session"""
    session_id = get_session_id()
    
    if session_id in download_progress:
        progress_data = download_progress[session_id].copy()
        
        # Clean up completed or errored downloads after some time
        if progress_data['status'] in ['completed', 'error']:
            elapsed = time.time() - progress_data.get('started_at', 0)
            if elapsed > 30:  # Clean up after 30 seconds
                del download_progress[session_id]
        
        return jsonify({
            'success': True,
            'progress': progress_data
        })
    else:
        return jsonify({
            'success': True,
            'progress': None
        })

@app.route('/api/cancel_download', methods=['POST'])
def cancel_download():
    """Cancel ongoing download"""
    session_id = get_session_id()
    
    # Clean up progress tracking
    if session_id in download_progress:
        del download_progress[session_id]
    
    # Note: We can't easily kill the ollama pull process, so we just clean up tracking
    if session_id in download_threads:
        del download_threads[session_id]
    
    return jsonify({'success': True, 'message': 'Download cancelled'})

@app.route('/api/get_popular_models', methods=['GET'])
def get_popular_models():
    """Get list of popular models for suggestions"""
    popular_models = [
        {
            'name': 'llama3.2:3b',
            'description': 'Latest Llama model, 3B parameters - Fast and efficient',
            'size': '2.0GB'
        },
        {
            'name': 'llama3.2:1b',
            'description': 'Smallest Llama model, 1B parameters - Very fast',
            'size': '1.3GB'
        },
        {
            'name': 'phi3:mini',
            'description': 'Microsoft Phi-3 Mini - Compact and capable',
            'size': '2.3GB'
        },
        {
            'name': 'gemma2:2b',
            'description': 'Google Gemma 2B - Balanced performance',
            'size': '1.6GB'
        },
        {
            'name': 'qwen2.5:3b',
            'description': 'Alibaba Qwen 2.5 - Multilingual support',
            'size': '2.0GB'
        },
        {
            'name': 'llava:7b',
            'description': 'Vision model - Can analyze images',
            'size': '4.7GB'
        },
        {
            'name': 'codellama:7b',
            'description': 'Specialized for code generation',
            'size': '3.8GB'
        },
        {
            'name': 'mistral:7b',
            'description': 'Mistral 7B - Excellent general purpose model',
            'size': '4.1GB'
        }
    ]
    
    return jsonify({
        'success': True,
        'models': popular_models
    })

# Session cleanup on app context teardown
@app.teardown_appcontext
def cleanup_session(error):
    """Optional cleanup when app context tears down"""
    pass

if __name__ == '__main__':
    from multiprocessing import freeze_support
    freeze_support()
    s = socket.socket()
    s.bind(('', 0))
    port = s.getsockname()[1]
    print("=== Ollama Chat UI with Complete Model & Character Management ===")
    print(f"Available Chat Models ({len(chat_models)}): {chat_models}")
    print(f"Available Caption Models ({len(caption_models)}): {caption_models}")
    print(f"Default Chat Model: {selected_chat_model}")
    print(f"Default Image Model: {selected_image_model}")
    print("🚀 Starting Flask server with session support on http://localhost:5000")
    print("👥 Multiple users can now use the app simultaneously without interference")
    print("📥 Complete model management: list, download, delete with persistent progress")
    print("🎭 Complete character management: create, edit, delete with full customization")
    print("🔧 Use the TEST OLLAMA button to debug download issues")
    app.run(debug=True, host='0.0.0.0', port=port)
