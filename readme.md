# Multi Model AI chat App
- An AI chat app, where you can create your characters and chat with them. Download models that you wish with in build model manager. You can even share images with your AI character and see reactions. I created this app in WSL and you will need Ollama cli to run this.

## Features
- Single Server Architecture - React and Flask served from one port
- Real-time Chat - Instant message display with typing indicators
- Multiple AI Models - Automatic discovery of chat and vision models
- Character Management - Create custom AI personalities
- Model Management - Download models as per your choice
- Image Processing - Upload and analyze images with vision models
- Rich Text Rendering - Full markdown support with syntax highlighting
- Dark/Light Mode - Toggle between themes with persistence
- No Page Reloads - Smooth single-page application experience
- Copy Code Blocks - One-click code copying functionality

## Screenshots
![Main Screen](screenshots/ss.png)
![Character Creation](screenshots/character_creation_ss.png)

## Recommended System Requirements
- 16GB RAM
- CUDA GPU 8GB VRAM

## Tech Stack Used:
- Flask
- React.js
- Tailwind CSS
- Ollama for LLM

## Models Recommended:
- Gemma3 4B
- Joycaption or BLIP for image captioning

## How to setup locally
- Step 1 install Ollama in your device [Ollama](https://ollama.com/download)
- Step 2 download LLM, use command `ollama run model_name` you can find [Models](https://ollama.com/search)
- Step 3 Download model for image captioning I recommend joycaption
- Step 4 `pip install -r requirements.txt`
- Step 5 `python app.py`

## Future Plans
- Maybe containerise it, if you know how to containerise it please do contribute
- Add chat saving system into local storage