/**
 * API client for Agenty backend
 * Handles all communication with the backend API endpoints
 */

import Utils from './utils.js';

const API = {
    // Base URL for API requests
    BASE_URL: '/api',
    
    // Default request headers
    DEFAULT_HEADERS: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    },
    
    /**
     * Make a fetch request with error handling
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @returns {Promise} Promise resolving to response data
     */
    async fetch(url, options = {}) {
        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    ...this.DEFAULT_HEADERS,
                    ...options.headers
                }
            });
            
            // Check if response is ok (status 200-299)
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw {
                    status: response.status,
                    statusText: response.statusText,
                    data: errorData
                };
            }
            
            // Parse JSON response
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('API request failed:', error);
            
            // Format error message for display
            let errorMessage = 'Wystąpił błąd podczas komunikacji z serwerem.';
            
            if (error.data && error.data.error) {
                errorMessage = error.data.error;
            } else if (error.status === 404) {
                errorMessage = 'Zasób nie został znaleziony.';
            } else if (error.status === 401) {
                errorMessage = 'Brak autoryzacji. Zaloguj się ponownie.';
            } else if (error.status === 403) {
                errorMessage = 'Brak uprawnień do wykonania tej operacji.';
            } else if (error.status === 400) {
                errorMessage = 'Nieprawidłowe dane.';
                if (error.data && error.data.errors) {
                    const errorDetails = Object.values(error.data.errors).flat().join(', ');
                    errorMessage += ` ${errorDetails}`;
                }
            } else if (error.status >= 500) {
                errorMessage = 'Wystąpił błąd serwera. Spróbuj ponownie później.';
            }
            
            // Show toast notification
            Utils.showToast(errorMessage, 'error');
            
            // Rethrow error for handling in components
            throw {
                message: errorMessage,
                originalError: error
            };
        }
    },
    
    /**
     * Get list of available agents
     * @returns {Promise} Promise resolving to agents list
     */
    async getAgents() {
        return this.fetch(`${this.BASE_URL}/agents/`);
    },

    /**
     * Get list of conversations
     * @returns {Promise} Promise resolving to conversations list
     */
    async getConversations() {
        const response = await this.fetch(`${this.BASE_URL}/conversations/`);
        return response.success ? response.conversations : [];
    },
    
    /**
     * Create a new conversation with an agent
     * @param {string} agentName - Name of the agent
     * @param {string} title - Optional conversation title
     * @returns {Promise} Promise resolving to new conversation data
     */
    async createConversation(agentName, title = null) {
        return this.fetch(`${this.BASE_URL}/conversations/create/`, {
            method: 'POST',
            body: JSON.stringify({
                agent_name: agentName,
                title: title
            })
        });
    },
    
    /**
     * Get conversation history
     * @param {string} sessionId - Conversation session ID
     * @param {number} limit - Maximum number of messages to retrieve
     * @returns {Promise} Promise resolving to conversation history
     */
    async getConversationHistory(sessionId, limit = 50) {
        return this.fetch(`${this.BASE_URL}/conversations/${sessionId}/history/?limit=${limit}`);
    },
    
    /**
     * Get conversation information
     * @param {string} sessionId - Conversation session ID
     * @returns {Promise} Promise resolving to conversation info
     */
    async getConversationInfo(sessionId) {
        return this.fetch(`${this.BASE_URL}/conversations/${sessionId}/info/`);
    },
    
    /**
     * Send message to chat
     * @param {string} sessionId - Conversation session ID
     * @param {string} message - Message content
     * @returns {Promise} Promise resolving to agent response
     */
    async sendChatMessage(sessionId, message) {
        return this.fetch(`${this.BASE_URL}/chat/message/`, {
            method: 'POST',
            body: JSON.stringify({
                session_id: sessionId,
                message: message
            })
        });
    },
    
    /**
     * Search for products
     * @param {string} query - Search query
     * @returns {Promise} Promise resolving to search results
     */
    async searchProducts(query) {
        return this.fetch(`${this.BASE_URL}/products/search/?q=${encodeURIComponent(query)}`);
    },
    
    /**
     * Upload receipt for processing
     * @param {File} file - Receipt file (PDF, JPG, PNG)
     * @param {Function} progressCallback - Callback for upload progress
     * @returns {Promise} Promise resolving to upload result
     */
    async uploadReceipt(file, progressCallback = null) {
        const formData = new FormData();
        formData.append('file', file);
        
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Track upload progress
            if (progressCallback) {
                xhr.upload.addEventListener('progress', (event) => {
                    if (event.lengthComputable) {
                        const percentComplete = Math.round((event.loaded / event.total) * 100);
                        progressCallback(percentComplete);
                    }
                });
            }
            
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve(data);
                    } catch (e) {
                        reject({
                            message: 'Błąd parsowania odpowiedzi serwera',
                            originalError: e
                        });
                    }
                } else {
                    let errorMessage = 'Wystąpił błąd podczas przesyłania paragonu.';
                    try {
                        const errorData = JSON.parse(xhr.responseText);
                        if (errorData.error) {
                            errorMessage = errorData.error;
                        }
                    } catch (e) {
                        // Ignore JSON parse errors
                    }
                    
                    reject({
                        message: errorMessage,
                        status: xhr.status
                    });
                    
                    // Show toast notification
                    Utils.showToast(errorMessage, 'error');
                }
            });
            
            xhr.addEventListener('error', () => {
                const errorMessage = 'Wystąpił błąd sieci podczas przesyłania paragonu.';
                reject({
                    message: errorMessage
                });
                
                // Show toast notification
                Utils.showToast(errorMessage, 'error');
            });
            
            xhr.open('POST', `${this.BASE_URL}/receipts/upload/`);
            xhr.send(formData);
        });
    },
    
    /**
     * Check receipt processing status
     * @param {number} receiptId - Receipt ID
     * @returns {Promise} Promise resolving to receipt status
     */
    async getReceiptStatus(receiptId) {
        return this.fetch(`${this.BASE_URL}/receipts/${receiptId}/status/`);
    },
    
    /**
     * Get recent receipts list
     * @param {number} limit - Maximum number of receipts to retrieve
     * @returns {Promise} Promise resolving to receipts list
     */
    async getRecentReceipts(limit = 10) {
        const response = await this.fetch(`${this.BASE_URL}/receipts/?limit=${limit}`);
        return response.success ? response.receipts : [];
    },
    
    /**
     * Consume inventory item
     * @param {number} inventoryId - Inventory item ID
     * @param {number} quantity - Quantity to consume
     * @param {string} notes - Optional notes
     * @returns {Promise} Promise resolving to consumption result
     */
    async consumeInventoryItem(inventoryId, quantity, notes = '') {
        return this.fetch(`${this.BASE_URL}/inventory/${inventoryId}/consume/`, {
            method: 'POST',
            body: JSON.stringify({
                consumed_qty: quantity,
                notes: notes
            })
        });
    },
    
    /**
     * Get inventory items
     * @param {Object} filters - Optional filters
     * @returns {Promise} Promise resolving to inventory items
     */
    async getInventoryItems(filters = {}) {
        // Build query string from filters
        const queryParams = Object.entries(filters)
            .filter(([_, value]) => value !== null && value !== undefined && value !== '')
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
            .join('&');

        const queryString = queryParams ? `?${queryParams}` : '';

        const response = await this.fetch(`${this.BASE_URL}/inventory/items/${queryString}`);
        return response.success ? response.items : [];
    },
    
    /**
     * Add new inventory item
     * @param {Object} itemData - Item data
     * @returns {Promise} Promise resolving to new item
     */
    async addInventoryItem(itemData) {
        // Note: This endpoint would need to be added to the backend
        return this.fetch(`${this.BASE_URL}/inventory/items/`, {
            method: 'POST',
            body: JSON.stringify(itemData)
        });
    },
    
    /**
     * Get inventory statistics
     * @returns {Promise} Promise resolving to inventory statistics
     */
    async getInventoryStatistics() {
        const response = await this.fetch(`${this.BASE_URL}/inventory/statistics/`);
        return response.success ? response.statistics : {};
    },

    /**
     * Get expiring items
     * @param {number} days - Days threshold
     * @returns {Promise} Promise resolving to expiring items
     */
    async getExpiringItems(days = 7) {
        const response = await this.fetch(`${this.BASE_URL}/inventory/expiring/?days=${days}`);
        return response.success ? response.items : [];
    },

    /**
     * Get analytics data
     * @param {string} timeRange - Time range for analytics
     * @returns {Promise} Promise resolving to analytics data
     */
    async getAnalyticsData(timeRange = '30days') {
        const response = await this.fetch(`${this.BASE_URL}/analytics/?time_range=${timeRange}`);
        return response.success ? response.analytics : {};
    },

    /**
     * Get top purchased products
     * @param {number} limit - Maximum number of products
     * @returns {Promise} Promise resolving to top products
     */
    async getTopProducts(limit = 10) {
        const response = await this.fetch(`${this.BASE_URL}/analytics/top-products/?limit=${limit}`);
        return response.success ? response.analytics.top_products : [];
    },

    /**
     * Get waste tracking data
     * @returns {Promise} Promise resolving to waste data
     */
    async getWasteData() {
        const response = await this.fetch(`${this.BASE_URL}/analytics/waste/`);
        return response.success ? response.analytics : { waste_items: 0 };
    },
    
    /**
     * Upload document for RAG processing
     * @param {File} file - Document file
     * @param {Function} progressCallback - Callback for upload progress
     * @returns {Promise} Promise resolving to upload result
     */
    async uploadDocument(file, progressCallback = null) {
        const formData = new FormData();
        formData.append('file', file);
        
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            
            // Track upload progress
            if (progressCallback) {
                xhr.upload.addEventListener('progress', (event) => {
                    if (event.lengthComputable) {
                        const percentComplete = Math.round((event.loaded / event.total) * 100);
                        progressCallback(percentComplete);
                    }
                });
            }
            
            xhr.addEventListener('load', () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve(data);
                    } catch (e) {
                        reject({
                            message: 'Błąd parsowania odpowiedzi serwera',
                            originalError: e
                        });
                    }
                } else {
                    let errorMessage = 'Wystąpił błąd podczas przesyłania dokumentu.';
                    try {
                        const errorData = JSON.parse(xhr.responseText);
                        if (errorData.error) {
                            errorMessage = errorData.error;
                        }
                    } catch (e) {
                        // Ignore JSON parse errors
                    }
                    
                    reject({
                        message: errorMessage,
                        status: xhr.status
                    });
                    
                    // Show toast notification
                    Utils.showToast(errorMessage, 'error');
                }
            });
            
            xhr.addEventListener('error', () => {
                const errorMessage = 'Wystąpił błąd sieci podczas przesyłania dokumentu.';
                reject({
                    message: errorMessage
                });
                
                // Show toast notification
                Utils.showToast(errorMessage, 'error');
            });
            
            xhr.open('POST', `${this.BASE_URL}/documents/`);
            xhr.send(formData);
        });
    },
    
};

// Export API for ES6 modules
export default API;
