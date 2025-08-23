/**
 * Chat module for Agenty frontend
 * Handles conversation with AI assistant
 */

import Utils from './utils.js';
import API from './api.js';
import App from './app.js';

const ChatModule = {
    // State
    currentSession: null,
    isWaitingForResponse: false,
    conversations: [],
    
    // Initialize chat interface
    init: function() {
        console.log('Initializing chat module...');
        
        // Initialize event listeners
        this.initEventListeners();
        
        // Load conversations
        this.loadConversations();
        
        // Focus chat input
        this.focusInput();
    },
    
    // Initialize event listeners
    initEventListeners: function() {
        // Send message button
        const sendButton = document.getElementById('send-message-btn');
        if (sendButton) {
            sendButton.addEventListener('click', this.sendMessage.bind(this));
        }
        
        // Chat input (Enter key handling)
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            chatInput.addEventListener('keydown', (event) => {
                // Send message on Enter (without Shift)
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    this.sendMessage();
                }
                
                // Auto-resize textarea
                this.resizeTextarea(chatInput);
            });
            
            // Auto-resize on input
            chatInput.addEventListener('input', () => {
                this.resizeTextarea(chatInput);
            });
        }
        
        // New conversation button
        const newChatButton = document.getElementById('new-chat-btn');
        if (newChatButton) {
            newChatButton.addEventListener('click', this.startNewConversation.bind(this));
        }
        
        // File upload
        const fileUpload = document.getElementById('file-upload');
        if (fileUpload) {
            fileUpload.addEventListener('change', this.handleFileUpload.bind(this));
        }
    },
    
    // Auto-resize textarea based on content
    resizeTextarea: function(textarea) {
        // Reset height to auto to calculate proper scrollHeight
        textarea.style.height = 'auto';
        
        // Set height to scrollHeight
        const newHeight = Math.min(Math.max(textarea.scrollHeight, 36), 150);
        textarea.style.height = `${newHeight}px`;
    },
    
    // Load conversations from server
    loadConversations: async function() {
        const conversationList = document.getElementById('conversation-list');
        if (!conversationList) return;
        
        // Show loading state
        conversationList.innerHTML = '<li class="conversation-item"><span>Ładowanie rozmów...</span></li>';
        
        try {
            const response = await API.getConversations();
            this.conversations = response.conversations || [];
            this.renderConversationList(this.conversations);
            
            // Select first conversation if none selected
            if (!this.currentSession && this.conversations.length > 0) {
                this.selectConversation(this.conversations[0].id);
            }
        } catch (error) {
            console.error('Error loading conversations:', error);
            conversationList.innerHTML = '<li class="conversation-item"><span>Błąd ładowania rozmów</span></li>';
        }
    },
    
    // Render conversation list
    renderConversationList: function(conversations) {
        const conversationList = document.getElementById('conversation-list');
        if (!conversationList) return;
        
        // Clear list
        conversationList.innerHTML = '';
        
        if (conversations.length === 0) {
            conversationList.innerHTML = '<li class="conversation-item"><span>Brak rozmów</span></li>';
            return;
        }
        
        // Store conversations
        this.conversations = conversations;
        
        // Add conversations to list
        conversations.forEach(conversation => {
            const li = document.createElement('li');
            li.className = 'conversation-item';
            if (this.currentSession === conversation.id) {
                li.classList.add('active');
            }
            
            li.innerHTML = `
                <div class="conversation-title">${conversation.title || 'Nowa rozmowa'}</div>
                <div class="conversation-time">${Utils.timeAgo(conversation.timestamp)}</div>
            `;
            
            li.addEventListener('click', () => {
                this.selectConversation(conversation.id);
            });
            
            conversationList.appendChild(li);
        });
    },
    
    // Select a conversation
    selectConversation: function(conversationId) {
        // Set current session
        this.currentSession = conversationId;
        
        // Update active class in list
        const conversationItems = document.querySelectorAll('.conversation-item');
        conversationItems.forEach(item => {
            item.classList.remove('active');
            if (item.querySelector('.conversation-title').textContent === this.getConversationTitle(conversationId)) {
                item.classList.add('active');
            }
        });
        
        // Load conversation history
        this.loadConversationHistory(conversationId);
    },
    
    // Get conversation title by ID
    getConversationTitle: function(conversationId) {
        const conversation = this.conversations.find(conv => conv.id === conversationId);
        return conversation ? (conversation.title || 'Nowa rozmowa') : 'Nieznana rozmowa';
    },
    
    // Load conversation history
    loadConversationHistory: async function(conversationId) {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        // Show loading state
        messagesContainer.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Ładowanie rozmowy...</span></div>';
        
        try {
            const response = await API.getConversationHistory(conversationId);
            this.renderMessages(response.history || []);
            
            // Scroll to bottom
            this.scrollToBottom();
        } catch (error) {
            console.error('Error loading conversation history:', error);
            messagesContainer.innerHTML = '<div class="error-message">Błąd ładowania historii rozmowy</div>';
        }
    },
    
    // Render messages
    renderMessages: function(messages) {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        // Clear container (except welcome message)
        const welcomeMessage = messagesContainer.querySelector('.welcome-message');
        messagesContainer.innerHTML = '';
        
        // If no messages and first load, show welcome message
        if (messages.length === 0 && welcomeMessage) {
            messagesContainer.appendChild(welcomeMessage);
            return;
        }
        
        // Add messages
        messages.forEach(message => {
            this.addMessageToUI(message);
        });
    },
    
    // Add a single message to UI
    addMessageToUI: function(message) {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.role}`;
        
        // Create message bubble
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        bubble.innerHTML = message.content;
        
        // Create message time
        const timeDiv = document.createElement('div');
        timeDiv.className = 'message-time';
        timeDiv.textContent = Utils.formatDate(message.timestamp, true);
        
        // Assemble message
        messageDiv.appendChild(bubble);
        
        // Add file attachment if present
        if (message.file) {
            const fileDiv = document.createElement('div');
            fileDiv.className = 'message-file';
            
            const icon = document.createElement('i');
            icon.className = this.getFileIcon(message.file.type);
            
            const fileName = document.createElement('span');
            fileName.className = 'file-name';
            fileName.textContent = message.file.name;
            
            const fileSize = document.createElement('span');
            fileSize.className = 'file-size';
            fileSize.textContent = Utils.formatFileSize(message.file.size);
            
            fileDiv.appendChild(icon);
            fileDiv.appendChild(fileName);
            fileDiv.appendChild(fileSize);
            
            messageDiv.appendChild(fileDiv);
        }
        
        messageDiv.appendChild(timeDiv);
        
        // Add to container
        messagesContainer.appendChild(messageDiv);
        
        // Scroll to bottom
        this.scrollToBottom();
    },
    
    // Scroll messages container to bottom
    scrollToBottom: function() {
        const messagesContainer = document.getElementById('messages-container');
        if (messagesContainer) {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    },
    
    // Focus input field
    focusInput: function() {
        const chatInput = document.getElementById('chat-input');
        if (chatInput) {
            setTimeout(() => {
                chatInput.focus();
            }, 100);
        }
    },
    
    // Send message
    sendMessage: function() {
        // Get chat input
        const chatInput = document.getElementById('chat-input');
        if (!chatInput) return;
        
        // Get message text
        const message = chatInput.value.trim();
        
        // Don't send empty messages
        if (!message) return;
        
        // Check if waiting for response
        if (this.isWaitingForResponse) {
            Utils.showToast('Poczekaj na odpowiedź asystenta.', 'warning');
            return;
        }
        
        // Check if session exists, otherwise create one
        if (!this.currentSession) {
            this.startNewConversation(message);
            return;
        }
        
        // Clear input
        chatInput.value = '';
        
        // Reset textarea height
        this.resizeTextarea(chatInput);
        
        // Add message to UI
        this.addMessageToUI({
            role: 'user',
            content: message,
            timestamp: new Date()
        });
        
        // Set waiting state
        this.isWaitingForResponse = true;
        this.showTypingIndicator();
        
        // Send message to API
        (async () => {
            try {
                const response = await API.sendChatMessage(this.currentSession, message);
                
                // Hide typing indicator
                this.hideTypingIndicator();
                
                // Add response to UI
                this.addMessageToUI({
                    role: 'assistant',
                    content: response.response,
                    timestamp: new Date()
                });
                
                // Reset waiting state
                this.isWaitingForResponse = false;
            } catch (error) {
                console.error('Error sending message:', error);
                
                // Hide typing indicator
                this.hideTypingIndicator();
                
                // Show error message
                Utils.showToast('Błąd wysyłania wiadomości.', 'error');
                
                // Reset waiting state
                this.isWaitingForResponse = false;
            }
        })();
    },
    
    // Start a new conversation
    startNewConversation: async function(initialMessage = null) {
        try {
            const response = await API.createConversation('router', initialMessage ? Utils.truncateText(initialMessage, 30) : null);
            this.currentSession = response.session_id;
            
            // Reload conversations
            await this.loadConversations();
            
            // If initial message provided, send it
            if (initialMessage) {
                // Set in input
                const chatInput = document.getElementById('chat-input');
                if (chatInput) {
                    chatInput.value = initialMessage;
                    this.sendMessage();
                }
            }
        } catch (error) {
            console.error('Error creating conversation:', error);
            Utils.showToast('Błąd tworzenia nowej rozmowy.', 'error');
        }
    },
    
    // Handle file upload
    handleFileUpload: function(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        // Validate file
        const validTypes = ['application/pdf', 'image/jpeg', 'image/png'];
        if (!validTypes.includes(file.type)) {
            Utils.showToast('Nieprawidłowy format pliku. Obsługiwane formaty: PDF, JPG, PNG.', 'error');
            return;
        }
        
        // Max file size (10MB)
        if (file.size > 10 * 1024 * 1024) {
            Utils.showToast('Plik jest za duży. Maksymalny rozmiar: 10MB.', 'error');
            return;
        }
        
        // Add file message to UI
        this.addMessageToUI({
            role: 'user',
            content: `Analizuję plik: ${file.name}`,
            timestamp: new Date(),
            file: {
                name: file.name,
                type: file.type,
                size: file.size
            }
        });
        
        // Show typing indicator
        this.isWaitingForResponse = true;
        this.showTypingIndicator();
        
        // Reset file input
        event.target.value = '';
        
        // Upload document
        (async () => {
            try {
                // First, check if we have a session
                if (!this.currentSession) {
                    await this.startNewConversation(`Analizuję plik: ${file.name}`);
                }
                
                // Upload document
                const response = await API.uploadDocument(file, (progress) => {
                    console.log(`Upload progress: ${progress}%`);
                });
                
                // Hide typing indicator
                this.hideTypingIndicator();
                
                // Add response to UI
                this.addMessageToUI({
                    role: 'assistant',
                    content: response.message || `Przeanalizowałem plik ${file.name}.`,
                    timestamp: new Date()
                });
                
                // Reset waiting state
                this.isWaitingForResponse = false;
            } catch (error) {
                console.error('Error uploading file:', error);
                
                // Hide typing indicator
                this.hideTypingIndicator();
                
                // Show error message
                Utils.showToast('Błąd przesyłania pliku.', 'error');
                
                // Reset waiting state
                this.isWaitingForResponse = false;
            }
        })();
    },
    
    // Show typing indicator
    showTypingIndicator: function() {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        // Remove existing typing indicator
        this.hideTypingIndicator();
        
        // Create typing indicator
        const typingIndicator = document.createElement('div');
        typingIndicator.className = 'message assistant typing-indicator';
        typingIndicator.innerHTML = `
            <div class="message-bubble">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        // Add to container
        messagesContainer.appendChild(typingIndicator);
        
        // Scroll to bottom
        this.scrollToBottom();
    },
    
    // Hide typing indicator
    hideTypingIndicator: function() {
        const typingIndicator = document.querySelector('.typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    },
    
    // Get file icon based on type
    getFileIcon: function(fileType) {
        if (fileType.includes('pdf')) {
            return 'fas fa-file-pdf';
        } else if (fileType.includes('image')) {
            return 'fas fa-file-image';
        } else if (fileType.includes('word')) {
            return 'fas fa-file-word';
        } else if (fileType.includes('excel') || fileType.includes('spreadsheet')) {
            return 'fas fa-file-excel';
        } else {
            return 'fas fa-file';
        }
    }
};

// Initialize module when page is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize only if chat page is active
    if (window.location.hash === '#chat') {
        ChatModule.init();
    }
    
    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        if (window.location.hash === '#chat') {
            ChatModule.init();
        }
    });
});

// Export for ES6 modules
export default ChatModule;
