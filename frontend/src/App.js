import React, { useState, useEffect, useRef } from 'react';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

export default function ChatApp() {
  // State management
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(() => {
    const stored = localStorage.getItem('darkMode');
    return stored === null ? true : stored === 'true';
  });
  
  // Models and Characters
  const [chatModels, setChatModels] = useState([]);
  const [captionModels, setCaptionModels] = useState([]);
  const [characters, setCharacters] = useState([]);
  const [selectedChatModel, setSelectedChatModel] = useState('');
  const [selectedCaptionModel, setSelectedCaptionModel] = useState('');
  const [selectedCharacter, setSelectedCharacter] = useState('');
  
  // UI State
  const [showCreateCharacterModal, setShowCreateCharacterModal] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState('');
  
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTyping]);

  // Apply dark mode
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
    localStorage.setItem('darkMode', isDarkMode);
  }, [isDarkMode]);

  // Fetch initial data
  useEffect(() => {
    fetchInitialData();
  }, []);

  const fetchInitialData = async () => {
    try {
      const response = await fetch(`${API_BASE}/get_initial_data`);
      const data = await response.json();
      if (data.success) {
        setChatModels(data.chat_models || []);
        setCaptionModels(data.caption_models || []);
        setCharacters(data.characters || []);
        setSelectedChatModel(data.selected_chat_model || '');
        setSelectedCaptionModel(data.selected_caption_model || '');
      }
    } catch (error) {
      console.error('Failed to fetch initial data:', error);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || isLoading || !selectedCharacter) return;
    
    const messageText = inputValue.trim();
    const userMessage = {
      id: Date.now(),
      sender: 'user',
      content: messageText,
      timestamp: new Date().toISOString()
    };

    // Add user message immediately
    setMessages(prev => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);
    setIsTyping(true);

    try {
      const response = await fetch(`${API_BASE}/send_message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: messageText })
      });
      
      const data = await response.json();
      setIsTyping(false);
      
      const botMessage = {
        id: Date.now() + 1,
        sender: 'bot',
        content: data.success ? data.response : `Error: ${data.error}`,
        timestamp: new Date().toISOString(),
        isError: !data.success
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      setIsTyping(false);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        sender: 'bot',
        content: 'Failed to send message. Please try again.',
        timestamp: new Date().toISOString(),
        isError: true
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const selectChatModel = async (model) => {
    setSelectedChatModel(model);
    setDropdownOpen('');
    try {
      await fetch(`${API_BASE}/select_chat_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model })
      });
    } catch (error) {
      console.error('Failed to select chat model:', error);
    }
  };

  const selectCaptionModel = async (model) => {
    setSelectedCaptionModel(model);
    setDropdownOpen('');
    try {
      await fetch(`${API_BASE}/select_image_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model })
      });
    } catch (error) {
      console.error('Failed to select caption model:', error);
    }
  };

  const selectCharacter = async (character) => {
    setSelectedCharacter(character);
    setDropdownOpen('');
    setMessages([]); // Clear messages when switching characters
    
    try {
      const response = await fetch(`${API_BASE}/select_character`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ character })
      });
      const data = await response.json();
      if (!data.success) {
        console.error('Failed to select character:', data.message);
      }
    } catch (error) {
      console.error('Failed to select character:', error);
    }
  };

  const createCharacter = async (characterData) => {
    try {
      const response = await fetch(`${API_BASE}/create_character`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(characterData)
      });
      
      const data = await response.json();
      if (data.success) {
        setCharacters(prev => [...prev, { name: characterData.name }]);
        setShowCreateCharacterModal(false);
        selectCharacter(characterData.name);
      } else {
        alert(data.message || 'Failed to create character');
      }
    } catch (error) {
      console.error('Failed to create character:', error);
      alert('Failed to create character');
    }
  };

  const uploadFile = async (file) => {
    if (!file || !selectedCharacter) return;

    const userMessage = {
      id: Date.now(),
      sender: 'user',
      content: `[Uploaded image: ${file.name}]`,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch(`${API_BASE}/upload_image`, {
        method: 'POST',
        body: formData
      });
      
      const data = await response.json();
      setIsTyping(false);
      
      if (data.success) {
        setMessages(prev => [...prev, {
          id: Date.now() + 1,
          sender: 'bot',
          content: data.response,
          imageCaption: data.caption,
          timestamp: new Date().toISOString()
        }]);
      } else {
        alert(data.error || 'Failed to process image');
      }
    } catch (error) {
      setIsTyping(false);
      console.error('Failed to upload image:', error);
      alert('Failed to upload image');
    }
  };

  const resetChat = async () => {
    if (!window.confirm('Are you sure you want to reset the chat?')) return;
    
    setMessages([]);
    try {
      await fetch(`${API_BASE}/reset_chat`, { method: 'POST' });
    } catch (error) {
      console.error('Failed to reset chat:', error);
    }
  };

  const refreshModels = async () => {
    try {
      const response = await fetch(`${API_BASE}/refresh_models`, { method: 'POST' });
      const data = await response.json();
      if (data.success) {
        setChatModels(data.chat_models);
        setCaptionModels(data.caption_models);
      }
    } catch (error) {
      console.error('Failed to refresh models:', error);
    }
  };

  return (
    <div className={`chat-app ${isDarkMode ? 'dark' : ''}`}>
      <div className="chat-container">
        {/* Sidebar */}
        <aside className="sidebar">
          <h2 className="sidebar-title">OPTIONS</h2>
          
          {/* Chat Model Dropdown */}
          <div className="dropdown-section">
            <label>AI CHAT MODEL</label>
            <div className="dropdown">
              <button 
                className="dropdown-button"
                onClick={() => setDropdownOpen(dropdownOpen === 'chat' ? '' : 'chat')}
              >
                <span>{selectedChatModel || 'Select Model'}</span>
                <svg className={`dropdown-arrow ${dropdownOpen === 'chat' ? 'open' : ''}`} viewBox="0 0 24 24">
                  <path d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              {dropdownOpen === 'chat' && (
                <div className="dropdown-menu">
                  {chatModels.map(model => (
                    <button key={model} onClick={() => selectChatModel(model)}>
                      {model}
                    </button>
                  ))}
                  <div className="dropdown-divider" />
                  <button onClick={refreshModels}>🔄 Refresh Models</button>
                </div>
              )}
            </div>
          </div>

          {/* Caption Model Dropdown */}
          <div className="dropdown-section">
            <label>IMAGE CAPTION MODEL</label>
            <div className="dropdown">
              <button 
                className="dropdown-button"
                onClick={() => setDropdownOpen(dropdownOpen === 'caption' ? '' : 'caption')}
              >
                <span>{selectedCaptionModel || 'Select Model'}</span>
                <svg className={`dropdown-arrow ${dropdownOpen === 'caption' ? 'open' : ''}`} viewBox="0 0 24 24">
                  <path d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              {dropdownOpen === 'caption' && (
                <div className="dropdown-menu">
                  {captionModels.map(model => (
                    <button key={model} onClick={() => selectCaptionModel(model)}>
                      {model}
                    </button>
                  ))}
                  <div className="dropdown-divider" />
                  <button onClick={refreshModels}>🔄 Refresh Models</button>
                </div>
              )}
            </div>
          </div>

          {/* Character Dropdown */}
          <div className="dropdown-section">
            <label>CHARACTER</label>
            <div className="dropdown">
              <button 
                className="dropdown-button"
                onClick={() => setDropdownOpen(dropdownOpen === 'character' ? '' : 'character')}
              >
                <span>{selectedCharacter || 'Select Character'}</span>
                <svg className={`dropdown-arrow ${dropdownOpen === 'character' ? 'open' : ''}`} viewBox="0 0 24 24">
                  <path d="M19 9l-7 7-7-7"/>
                </svg>
              </button>
              {dropdownOpen === 'character' && (
                <div className="dropdown-menu">
                  {characters.map(char => (
                    <button key={char.name} onClick={() => selectCharacter(char.name)}>
                      {char.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Action Buttons */}
          <button 
            className="action-button"
            onClick={() => setShowCreateCharacterModal(true)}
          >
            CREATE CHARACTER
          </button>
          
          <button className="action-button reset-button" onClick={resetChat}>
            RESET CHAT
          </button>

          {/* Dark Mode Toggle */}
          <div className="dark-mode-toggle">
            <label>DARK MODE</label>
            <button 
              className={`toggle-switch ${isDarkMode ? 'active' : ''}`}
              onClick={() => setIsDarkMode(!isDarkMode)}
            >
              <div className="toggle-slider" />
            </button>
          </div>
        </aside>

        {/* Main Chat Area */}
        <main className="chat-main">
          <h1 className="chat-title">{selectedCharacter || 'CHARACTER NAME'}</h1>
          
          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="welcome-message">
                <p>👋 Welcome to Ollama Chat UI!</p>
                <p>Select a character and start chatting</p>
              </div>
            ) : (
              messages.map(message => (
                <div 
                  key={message.id} 
                  className={`message ${message.sender} ${message.isError ? 'error' : ''}`}
                >
                  <div className="message-content">
                    {message.content}
                    {message.imageCaption && (
                      <div className="image-caption">
                        Caption: {message.imageCaption}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            
            {isTyping && (
              <div className="message bot typing">
                <div className="typing-indicator">
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                  <div className="typing-dot" />
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="input-container">
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => e.target.files[0] && uploadFile(e.target.files[0])}
              accept="image/*"
              style={{ display: 'none' }}
            />
            
            <button 
              className="upload-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={!selectedCharacter}
            >
              <svg viewBox="0 0 24 24">
                <path d="M12 4v16m8-8H4"/>
              </svg>
            </button>
            
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Type a message..."
              disabled={isLoading || !selectedCharacter}
              className="message-input"
            />
            
            <button 
              onClick={sendMessage}
              disabled={isLoading || !inputValue.trim() || !selectedCharacter}
              className="send-button"
            >
              {isLoading ? (
                <div className="spinner" />
              ) : (
                <svg viewBox="0 0 24 24">
                  <path d="M8 7l4-4m0 0l4 4m-4-4v18"/>
                </svg>
              )}
            </button>
          </div>
        </main>
      </div>

      {/* Character Creation Modal */}
      {showCreateCharacterModal && (
        <CharacterModal 
          onClose={() => setShowCreateCharacterModal(false)}
          onSubmit={createCharacter}
        />
      )}
    </div>
  );
}

// Character Creation Modal Component
function CharacterModal({ onClose, onSubmit }) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    image_caption_prompt: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name.trim()) {
      alert('Character name is required');
      return;
    }
    onSubmit(formData);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Create Character</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>Name *</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({...formData, name: e.target.value})}
              placeholder="Enter character name"
              required
            />
          </div>
          
          <div className="form-group">
            <label>Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              placeholder="Enter character description and personality traits"
              rows="3"
            />
          </div>
          
          <div className="form-group">
            <label>Image Caption Prompt</label>
            <textarea
              value={formData.image_caption_prompt}
              onChange={(e) => setFormData({...formData, image_caption_prompt: e.target.value})}
              placeholder="Enter prompt for image captioning"
              rows="2"
            />
          </div>
          
          <div className="modal-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit">Create Character</button>
          </div>
        </form>
      </div>
    </div>
  );
}
