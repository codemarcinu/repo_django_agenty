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
    loadConversations: function() {
        const conversationList = document.getElementById('conversation-list');
        if (!conversationList) return;
        
        // Show loading state
        conversationList.innerHTML = '<li class="conversation-item"><span>Ładowanie rozmów...</span></li>';
        
        // For demo purposes, use mock data
        setTimeout(() => {
            const mockConversations = [
                { id: 'conv-1', title: 'Rozmowa o spożarni', timestamp: new Date(2025, 7, 20, 14, 30) },
                { id: 'conv-2', title: 'Pytania o paragony', timestamp: new Date(2025, 7, 22, 9, 15) }
            ];
            
            this.renderConversationList(mockConversations);
            
            // Select first conversation if none selected
            if (!this.currentSession && mockConversations.length > 0) {
                this.selectConversation(mockConversations[0].id);
            }
        }, 500);
        
        // In a real implementation, we would use:
        // try {
        //     const response = await API.getConversations();
        //     this.conversations = response.conversations;
        //     this.renderConversationList(this.conversations);
        // } catch (error) {
        //     console.error('Error loading conversations:', error);
        //     conversationList.innerHTML = '<li class="conversation-item"><span>Błąd ładowania rozmów</span></li>';
        // }
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
    loadConversationHistory: function(conversationId) {
        const messagesContainer = document.getElementById('messages-container');
        if (!messagesContainer) return;
        
        // Show loading state
        messagesContainer.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Ładowanie rozmowy...</span></div>';
        
        // For demo purposes, use mock data
        setTimeout(() => {
            let mockMessages = [];
            
            if (conversationId === 'conv-1') {
                mockMessages = [
                    { role: 'user', content: 'Cześć, co mam w spiżarni?', timestamp: new Date(2025, 7, 20, 14, 30) },
                    { role: 'assistant', content: 'Cześć! W Twojej spiżarni masz obecnie 15 produktów. Najbliższe terminy ważności to: Mleko (2 dni), Chleb (3 dni). Czy chcesz zobaczyć pełną listę?', timestamp: new Date(2025, 7, 20, 14, 31) },
                    { role: 'user', content: 'Tak, pokaż mi pełną listę', timestamp: new Date(2025, 7, 20, 14, 31) },
                    { role: 'assistant', content: 'Oto pełna lista produktów w Twojej spiżarni:<br><br>1. Mleko 3.2% - 1.5l (ważne przez 2 dni)<br>2. Chleb pszenny - 1 szt. (ważne przez 3 dni)<br>3. Jogurt naturalny - 4 szt. (ważne przez 9 dni)<br>4. Ser żółty - 250g (ważne przez 5 dni)<br>5. Masło - 200g (ważne przez 7 dni)<br>6. Jajka - 10 szt. (ważne przez 14 dni)<br>7. Pomidory - 500g (ważne przez 4 dni)<br>8. Ogórki - 3 szt. (ważne przez 5 dni)<br>9. Jabłka - 1kg (ważne przez 10 dni)<br>10. Banany - 6 szt. (ważne przez 3 dni)<br><br>Chcesz zobaczyć więcej produktów lub filtrować według lokalizacji?', timestamp: new Date(2025, 7, 20, 14, 32) }
                ];
            } else if (conversationId === 'conv-2') {
                mockMessages = [
                    { role: 'user', content: 'Jak przesłać paragon?', timestamp: new Date(2025, 7, 22, 9, 15) },
                    { role: 'assistant', content: 'Możesz przesłać paragon na kilka sposobów:<br><br>1. Przejdź do sekcji "Paragony" w menu bocznym<br>2. Przeciągnij i upuść plik paragonu (zdjęcie lub PDF) w obszarze przesyłania<br>3. Lub kliknij przycisk "Wybierz plik" i wybierz plik z dysku<br><br>Obsługiwane formaty to: JPG, PNG, PDF. System automatycznie rozpozna produkty i doda je do Twojej spiżarni. Czy potrzebujesz więcej szczegółów?', timestamp: new Date(2025, 7, 22, 9, 16) }
                ];
            }
            
            this.renderMessages(mockMessages);
            
            // Scroll to bottom
            this.scrollToBottom();
        }, 500);
        
        // In a real implementation, we would use:
        // try {
        //     const response = await API.getConversationHistory(conversationId);
        //     this.renderMessages(response.history);
        // } catch (error) {
        //     console.error('Error loading conversation history:', error);
        //     messagesContainer.innerHTML = '<div class="error-message">Błąd ładowania historii rozmowy</div>';
        // }
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
        
        // For demo purposes, simulate API call
        setTimeout(() => {
            // Generate mock response
            let response;
            
            if (message.toLowerCase().includes('spiżarni') || message.toLowerCase().includes('lodowce') || message.toLowerCase().includes('produkty')) {
                response = 'W Twojej spiżarni masz obecnie 15 produktów. Najbliższe terminy ważności to: Mleko (2 dni), Chleb (3 dni). Czy chcesz zobaczyć pełną listę?';
            } else if (message.toLowerCase().includes('paragon')) {
                response = 'Możesz przesłać paragon w sekcji "Paragony". Po załadowaniu zdjęcia system automatycznie rozpozna produkty i doda je do Twojej spiżarni.';
            } else if (message.toLowerCase().includes('pogoda')) {
                response = 'Aktualna pogoda w Warszawie: 23°C, częściowe zachmurzenie. Prognoza na jutro: 25°C, słonecznie.';
            } else {
                response = 'Rozumiem. Czy mogę pomóc Ci z czymś związanym z Twoją spiżarnią, paragonami lub czymś innym?';
            }
            
            // Remove typing indicator
            this.hideTypingIndicator();
            
            // Add response to UI
            this.addMessageToUI({
                role: 'assistant',
                content: response,
                timestamp: new Date()
            });
            
            // Reset waiting state
            this.isWaitingForResponse = false;
        }, 1500);
        
        // In a real implementation, we would use:
        // try {
        //     const response = await API.sendChatMessage(this.currentSession, message);
        //     
        //     // Hide typing indicator
        //     this.hideTypingIndicator();
        //     
        //     // Add response to UI
        //     this.addMessageToUI({
        //         role: 'assistant',
        //         content: response.response,
        //         timestamp: new Date()
        //     });
        //     
        //     // Reset waiting state
        //     this.isWaitingForResponse = false;
        // } catch (error) {
        //     console.error('Error sending message:', error);
        //     
        //     // Hide typing indicator
        //     this.hideTypingIndicator();
        //     
        //     // Show error message
        //     Utils.showToast('Błąd wysyłania wiadomości.', 'error');
        //     
        //     // Reset waiting state
        //     this.isWaitingForResponse = false;
        // }
    },
    
    // Start a new conversation
    startNewConversation: function(initialMessage = null) {
        // Generate unique ID for demo
        const sessionId = 'conv-' + Date.now();
        
        // Add to conversations list
        this.conversations.unshift({
            id: sessionId,
            title: initialMessage ? Utils.truncateText(initialMessage, 30) : 'Nowa rozmowa',
            timestamp: new Date()
        });
        
        // Update UI
        this.renderConversationList(this.conversations);
        
        // Select the new conversation
        this.selectConversation(sessionId);
        
        // If initial message provided, send it
        if (initialMessage) {
            // Set in input
            const chatInput = document.getElementById('chat-input');
            if (chatInput) {
                chatInput.value = initialMessage;
                this.sendMessage();
            }
        }
        
        // In a real implementation, we would use:
        // try {
        //     const response = await API.createConversation('router', initialMessage ? Utils.truncateText(initialMessage, 30) : null);
        //     this.currentSession = response.session_id;
        //     
        //     // Reload conversations
        //     this.loadConversations();
        //     
        //     // If initial message provided, send it
        //     if (initialMessage) {
        //         // Set in input
        //         const chatInput = document.getElementById('chat-input');
        //         if (chatInput) {
        //             chatInput.value = initialMessage;
        //             this.sendMessage();
        //         }
        //     }
        // } catch (error) {
        //     console.error('Error creating conversation:', error);
        //     Utils.showToast('Błąd tworzenia nowej rozmowy.', 'error');
        // }
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
        
        // For demo purposes, simulate processing
        setTimeout(() => {
            // Remove typing indicator
            this.hideTypingIndicator();
            
            // Add response to UI
            this.addMessageToUI({
                role: 'assistant',
                content: `Przeanalizowałem plik ${file.name}. To wygląda na ${file.type.includes('pdf') ? 'dokument PDF' : 'zdjęcie'}. Czy chcesz, żebym przetworzył go jako paragon, czy jako dokument do analizy?`,
                timestamp: new Date()
            });
            
            // Reset waiting state
            this.isWaitingForResponse = false;
        }, 2000);
        
        // Reset file input
        event.target.value = '';
        
        // In a real implementation, we would use:
        // try {
        //     // First, check if we have a session
        //     if (!this.currentSession) {
        //         await this.startNewConversation(`Analizuję plik: ${file.name}`);
        //     } else {
        //         // Add file message to UI
        //         this.addMessageToUI({
        //             role: 'user',
        //             content: `Analizuję plik: ${file.name}`,
        //             timestamp: new Date(),
        //             file: {
        //                 name: file.name,
        //                 type: file.type,
        //                 size: file.size
        //             }
        //         });
        //     }
        //     
        //     // Show typing indicator
        //     this.isWaitingForResponse = true;
        //     this.showTypingIndicator();
        //     
        //     // Upload document
        //     const response = await API.uploadDocument(file, (progress) => {
        //         console.log(`Upload progress: ${progress}%`);
        //     });
        //     
        //     // Hide typing indicator
        //     this.hideTypingIndicator();
        //     
        //     // Add response to UI
        //     this.addMessageToUI({
        //         role: 'assistant',
        //         content: response.message || `Przeanalizowałem plik ${file.name}.`,
        //         timestamp: new Date()
        //     });
        //     
        //     // Reset waiting state
        //     this.isWaitingForResponse = false;
        // } catch (error) {
        //     console.error('Error uploading file:', error);
        //     
        //     // Hide typing indicator
        //     this.hideTypingIndicator();
        //     
        //     // Show error message
        //     Utils.showToast('Błąd przesyłania pliku.', 'error');
        //     
        //     // Reset waiting state
        //     this.isWaitingForResponse = false;
        // }
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
