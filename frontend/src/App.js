import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';
import './App.css';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

// Model Download Modal Component
function ModelDownloadModal({ onClose }) {
  const [modelName, setModelName] = useState('');
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadProgress, setDownloadProgress] = useState(null);
  const [popularModels, setPopularModels] = useState([]);
  const [showPopular, setShowPopular] = useState(true);

  useEffect(() => {
    // Fetch popular models
    const fetchPopularModels = async () => {
      try {
        const response = await fetch(`${API_BASE}/get_popular_models`, {
          credentials: 'include'
        });
        const data = await response.json();
        if (data.success) {
          setPopularModels(data.models);
        }
      } catch (error) {
        console.error('Failed to fetch popular models:', error);
      }
    };
    
    fetchPopularModels();
  }, []);

  useEffect(() => {
    let progressInterval;
    
    if (isDownloading) {
      progressInterval = setInterval(async () => {
        try {
          const response = await fetch(`${API_BASE}/download_progress`, {
            credentials: 'include'
          });
          const data = await response.json();
          
          if (data.success && data.progress) {
            setDownloadProgress(data.progress);
            
            if (data.progress.status === 'completed') {
              setIsDownloading(false);
              setTimeout(() => {
                setDownloadProgress(null);
                onClose();
                window.location.reload(); // Refresh to update model lists
              }, 2000);
            } else if (data.progress.status === 'error') {
              setIsDownloading(false);
            }
          }
        } catch (error) {
          console.error('Failed to fetch download progress:', error);
        }
      }, 1000);
    }
    
    return () => {
      if (progressInterval) {
        clearInterval(progressInterval);
      }
    };
  }, [isDownloading, onClose]);

  const handleDownload = async () => {
    if (!modelName.trim()) {
      alert('Please enter a model name');
      return;
    }

    setIsDownloading(true);
    setDownloadProgress({ status: 'starting', progress: 0, message: 'Starting download...' });

    try {
      const response = await fetch(`${API_BASE}/download_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ model_name: modelName.trim() })
      });

      const data = await response.json();
      if (!data.success) {
        alert(data.message);
        setIsDownloading(false);
        setDownloadProgress(null);
      }
    } catch (error) {
      console.error('Failed to start download:', error);
      alert('Failed to start download');
      setIsDownloading(false);
      setDownloadProgress(null);
    }
  };

  const handleCancel = async () => {
    try {
      await fetch(`${API_BASE}/cancel_download`, {
        method: 'POST',
        credentials: 'include'
      });
      setIsDownloading(false);
      setDownloadProgress(null);
    } catch (error) {
      console.error('Failed to cancel download:', error);
    }
  };

  const selectModel = (model) => {
    setModelName(model.name);
    setShowPopular(false);
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal download-modal" onClick={(e) => e.stopPropagation()}>
        <h2>Download Ollama Model</h2>
        
        {!isDownloading && showPopular && (
          <div className="popular-models">
            <h3>Popular Models</h3>
            <div className="popular-models-grid">
              {popularModels.map((model, index) => (
                <div 
                  key={index} 
                  className="popular-model-card"
                  onClick={() => selectModel(model)}
                >
                  <div className="model-name">{model.name}</div>
                  <div className="model-description">{model.description}</div>
                  <div className="model-size">Size: {model.size}</div>
                </div>
              ))}
            </div>
            <div className="modal-divider">
              <span>OR</span>
            </div>
          </div>
        )}

        <div className="form-group">
          <label>Model Name</label>
          <input
            type="text"
            value={modelName}
            onChange={(e) => setModelName(e.target.value)}
            placeholder="e.g., llama3.2:3b, phi3:mini, gemma2:2b"
            disabled={isDownloading}
          />
          <div className="model-name-help">
            Enter the full model name with tag (e.g., llama3.2:3b). 
            Check <a href="https://ollama.com/library" target="_blank" rel="noopener noreferrer">ollama.com/library</a> for available models.
          </div>
        </div>

        {downloadProgress && (
          <div className="download-progress">
            <div className="progress-info">
              <div className="progress-message">{downloadProgress.message}</div>
              <div className="progress-percent">{downloadProgress.progress}%</div>
            </div>
            <div className="progress-bar">
              <div 
                className="progress-fill" 
                style={{ width: `${downloadProgress.progress}%` }}
              />
            </div>
            {downloadProgress.status === 'error' && (
              <div className="progress-error">
                Download failed. Please try again.
              </div>
            )}
          </div>
        )}

        <div className="modal-actions">
          {isDownloading ? (
            <>
              <button type="button" onClick={handleCancel}>Cancel</button>
              <button type="button" disabled>Downloading...</button>
            </>
          ) : (
            <>
              <button type="button" onClick={onClose}>Close</button>
              <button type="button" onClick={handleDownload}>Download</button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

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
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState('');
  const [showMobileSidebar, setShowMobileSidebar] = useState(false);
  
  // Session Management
  const [sessionId, setSessionId] = useState(null);
  
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

  // Fetch initial data and initialize session
  useEffect(() => {
    fetchInitialData();
  }, []);

  // Close mobile sidebar when clicking outside or on selection
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth > 768) {
        setShowMobileSidebar(false);
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const fetchInitialData = async () => {
    try {
      const response = await fetch(`${API_BASE}/get_initial_data`, {
        method: 'GET',
        credentials: 'include' // IMPORTANT: include credentials for session cookie
      });
      const data = await response.json();
      if (data.success) {
        setSessionId(data.session_id);
        setChatModels(data.chat_models || []);
        setCaptionModels(data.caption_models || []);
        setCharacters(data.characters || []);
        setSelectedChatModel(data.selected_chat_model || '');
        setSelectedCaptionModel(data.selected_caption_model || '');
        
        console.log(`Session initialized: ${data.session_id.substring(0, 8)}... (${data.active_sessions} active sessions)`);
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
        credentials: 'include',
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
    setShowMobileSidebar(false);
    try {
      await fetch(`${API_BASE}/select_chat_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ model })
      });
    } catch (error) {
      console.error('Failed to select chat model:', error);
    }
  };

  const selectCaptionModel = async (model) => {
    setSelectedCaptionModel(model);
    setDropdownOpen('');
    setShowMobileSidebar(false);
    try {
      await fetch(`${API_BASE}/select_image_model`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ model })
      });
    } catch (error) {
      console.error('Failed to select caption model:', error);
    }
  };

  const selectCharacter = async (character) => {
    setSelectedCharacter(character);
    setDropdownOpen('');
    setMessages([]);
    setShowMobileSidebar(false);
    
    try {
      const response = await fetch(`${API_BASE}/select_character`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
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
        credentials: 'include',
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
        credentials: 'include',
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
      await fetch(`${API_BASE}/reset_chat`, { 
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('Failed to reset chat:', error);
    }
  };

  const refreshModels = async () => {
    try {
      const response = await fetch(`${API_BASE}/refresh_models`, { 
        method: 'POST',
        credentials: 'include'
      });
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
      {/* Mobile Sidebar Overlay */}
      {showMobileSidebar && (
        <div 
          className="mobile-overlay" 
          onClick={() => setShowMobileSidebar(false)}
        />
      )}

      <div className="chat-container">
        {/* Sidebar */}
        <aside className={`sidebar ${showMobileSidebar ? 'show-mobile' : ''}`}>
          <div className="mobile-sidebar-header">
            <h2 className="sidebar-title">OPTIONS</h2>
            <button 
              className="mobile-close-btn"
              onClick={() => setShowMobileSidebar(false)}
            >
              ✕
            </button>
          </div>
          
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
            onClick={() => {
              setShowCreateCharacterModal(true);
              setShowMobileSidebar(false);
            }}
          >
            CREATE CHARACTER
          </button>

          <button 
            className="action-button"
            onClick={() => {
              setShowDownloadModal(true);
              setShowMobileSidebar(false);
            }}
          >
            📥 DOWNLOAD MODEL
          </button>
          
          <button 
            className="action-button reset-button" 
            onClick={() => {
              resetChat();
              setShowMobileSidebar(false);
            }}
          >
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

          {/* Session Info (for debugging) */}
          {sessionId && (
            <div style={{ fontSize: '0.7rem', opacity: 0.7, marginTop: 'auto', paddingTop: '1rem' }}>
              Session: {sessionId.substring(0, 8)}...
            </div>
          )}
        </aside>

        {/* Main Chat Area */}
        <main className="chat-main">
          <div className="chat-header">
            <div className="mobile-menu-container">
              <button 
                className="mobile-menu-btn"
                onClick={() => setShowMobileSidebar(true)}
              >
                ☰ Menu
              </button>
            </div>
            <h1 className="chat-title">{selectedCharacter || 'CHARACTER NAME'}</h1>
          </div>
          
          <div className="messages-container">
            {messages.length === 0 ? (
              <div className="welcome-message">
                <p>👋 Welcome to Ollama Chat UI!</p>
                <p>Select a character and start chatting</p>
                {sessionId && (
                  <p style={{ fontSize: '0.8rem', opacity: 0.7, marginTop: '1rem' }}>
                    Your session: {sessionId.substring(0, 8)}...
                  </p>
                )}
              </div>
            ) : (
              messages.map(message => (
                <div 
                  key={message.id} 
                  className={`message ${message.sender} ${message.isError ? 'error' : ''}`}
                >
                  <div className="message-content">
                    <MessageContent 
                      content={message.content} 
                      sender={message.sender}
                    />
                    {message.imageCaption && (
                      <div className="image-caption">
                        <strong>Caption:</strong> {message.imageCaption}
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

          {/* Input Area - Updated with attachment inside */}
          <div className="input-container">
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => e.target.files[0] && uploadFile(e.target.files[0])}
              accept="image/*"
              style={{ display: 'none' }}
            />
            
            <div className="input-wrapper">
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
                className="attachment-button"
                onClick={() => fileInputRef.current?.click()}
                disabled={!selectedCharacter}
                title="Attach image"
                type="button"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66L9.64 16.2a2 2 0 0 1-2.83-2.83l8.49-8.48"/>
                </svg>
              </button>
            </div>
            
            <button 
              onClick={sendMessage}
              disabled={isLoading || !inputValue.trim() || !selectedCharacter}
              className="send-button"
              type="button"
            >
              {isLoading ? (
                <div className="spinner" />
              ) : (
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 2L11 13"/>
                  <path d="m22 2-7 20-4-9-9-4 20-7z"/>
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

      {/* Model Download Modal */}
      {showDownloadModal && (
        <ModelDownloadModal 
          onClose={() => setShowDownloadModal(false)}
        />
      )}
    </div>
  );
}

// Message Content Component with Markdown Support
function MessageContent({ content, sender }) {
  const components = {
    a: ({ node, ...props }) => (
      <a 
        {...props} 
        target="_blank" 
        rel="noopener noreferrer"
        className="message-link"
      />
    ),
    code: ({ node, inline, className, children, ...props }) => {
      const match = /language-(\w+)/.exec(className || '');
      return !inline ? (
        <div className="code-block-wrapper">
          <div className="code-block-header">
            <span className="code-language">{match ? match[1] : 'text'}</span>
            <button 
              onClick={() => navigator.clipboard.writeText(String(children))}
              className="copy-button"
              title="Copy code"
              type="button"
            >
              📋
            </button>
          </div>
          <code className={className} {...props}>
            {children}
          </code>
        </div>
      ) : (
        <code className="inline-code" {...props}>
          {children}
        </code>
      );
    },
    blockquote: ({ children }) => (
      <blockquote className="message-blockquote">
        {children}
      </blockquote>
    ),
    table: ({ children }) => (
      <div className="table-wrapper">
        <table className="message-table">
          {children}
        </table>
      </div>
    )
  };

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={components}
      className={`markdown-content ${sender === 'user' ? 'user-message' : 'bot-message'}`}
    >
      {content}
    </ReactMarkdown>
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
