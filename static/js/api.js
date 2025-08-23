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
     * Get authentication token from local storage
     * @returns {string|null} Auth token
     */
    getToken: function() {
        return localStorage.getItem('authToken');
    },

    /**
     * Perform user login
     * @param {string} username - The username
     * @param {string} password - The password
     * @returns {Promise} Promise resolving to login response data
     */
    async login(username, password) {
        // This request does not need a token
        const response = await this.fetch(`${this.BASE_URL}/token-auth/`, {
            method: 'POST',
            body: JSON.stringify({ username, password })
        }, false); // `false` indicates no token is required for this request

        if (response && response.token) {
            localStorage.setItem('authToken', response.token);
        }
        return response;
    },

    /**
     * Perform user logout
     */
    logout: function() {
        localStorage.removeItem('authToken');
    },
    
    /**
     * Make a fetch request with error handling and auth
     * @param {string} url - API endpoint URL
     * @param {Object} options - Fetch options
     * @param {boolean} sendToken - Whether to send the auth token
     * @returns {Promise} Promise resolving to response data
     */
    async fetch(url, options = {}, sendToken = true) {
        const headers = {
            ...this.DEFAULT_HEADERS,
            ...options.headers
        };

        if (sendToken) {
            const token = this.getToken();
            if (token) {
                headers['Authorization'] = `Token ${token}`;
            }
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers: headers
            });
            
            if (!response.ok) {
                if (response.status === 401) {
                    // Handle unauthorized access, e.g., by redirecting to login
                    this.logout();
                    window.location.reload();
                }
                const errorData = await response.json().catch(() => ({}));
                throw {
                    status: response.status,
                    statusText: response.statusText,
                    data: errorData
                };
            }
            
            return response.status === 204 ? {} : await response.json(); // Handle 204 No Content
        } catch (error) {
            console.error('API request failed:', error);
            
            let errorMessage = 'Wystąpił błąd podczas komunikacji z serwerem.';
            
            if (error.data && (error.data.error || error.data.detail)) {
                errorMessage = error.data.error || error.data.detail;
            } else if (error.status === 404) {
                errorMessage = 'Zasób nie został znaleziony.';
            } else if (error.status === 401) {
                errorMessage = 'Błędne dane logowania lub sesja wygasła.';
            } else if (error.status === 403) {
                errorMessage = 'Brak uprawnień do wykonania tej operacji.';
            } else if (error.status === 400) {
                errorMessage = 'Nieprawidłowe dane.';
                if (error.data) {
                    const errorDetails = Object.values(error.data).flat().join(', ');
                    errorMessage += ` ${errorDetails}`;
                }
            } else if (error.status >= 500) {
                errorMessage = 'Wystąpił błąd serwera. Spróbuj ponownie później.';
            }
            
            Utils.showToast(errorMessage, 'error');
            
            throw {
                message: errorMessage,
                originalError: error
            };
        }
    },
    
    /**
     * Create an authenticated XMLHttpRequest
     * @param {string} method - HTTP method
     * @param {string} url - API endpoint URL
     * @returns {XMLHttpRequest} Authenticated XHR object
     */
    createAuthenticatedXHR: function(method, url) {
        const xhr = new XMLHttpRequest();
        xhr.open(method, url);
        const token = this.getToken();
        if (token) {
            xhr.setRequestHeader('Authorization', `Token ${token}`);
        }
        return xhr;
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
            const xhr = this.createAuthenticatedXHR('POST', `${this.BASE_URL}/receipts/upload/`);
            
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
                        reject({ message: 'Błąd parsowania odpowiedzi serwera', originalError: e });
                    }
                } else {
                    let errorMessage = 'Wystąpił błąd podczas przesyłania paragonu.';
                    try {
                        const errorData = JSON.parse(xhr.responseText);
                        if (errorData.error || errorData.detail) {
                            errorMessage = errorData.error || errorData.detail;
                        }
                    } catch (e) {}
                    
                    reject({ message: errorMessage, status: xhr.status });
                    Utils.showToast(errorMessage, 'error');
                }
            });
            
            xhr.addEventListener('error', () => {
                const errorMessage = 'Wystąpił błąd sieci podczas przesyłania paragonu.';
                reject({ message: errorMessage });
                Utils.showToast(errorMessage, 'error');
            });
            
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
     * Delete receipt
     * @param {number} receiptId - Receipt ID to delete
     * @returns {Promise} Promise resolving to deletion result
     */
    async deleteReceipt(receiptId) {
        return this.fetch(`${this.BASE_URL}/receipts/${receiptId}/`, {
            method: 'DELETE'
        });
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
        try {
            const response = await this.fetch(`${this.BASE_URL}/analytics/?time_range=${timeRange}`);
            return response.success ? response.analytics : {};
        } catch (error) {
            console.error('Analytics API error:', error);
            return {};
        }
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
            const xhr = this.createAuthenticatedXHR('POST', `${this.BASE_URL}/documents/`);
            
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
                        reject({ message: 'Błąd parsowania odpowiedzi serwera', originalError: e });
                    }
                } else {
                    let errorMessage = 'Wystąpił błąd podczas przesyłania dokumentu.';
                    try {
                        const errorData = JSON.parse(xhr.responseText);
                        if (errorData.error || errorData.detail) {
                            errorMessage = errorData.error || errorData.detail;
                        }
                    } catch (e) {}
                    
                    reject({ message: errorMessage, status: xhr.status });
                    Utils.showToast(errorMessage, 'error');
                }
            });
            
            xhr.addEventListener('error', () => {
                const errorMessage = 'Wystąpił błąd sieci podczas przesyłania dokumentu.';
                reject({ message: errorMessage });
                Utils.showToast(errorMessage, 'error');
            });
            
            xhr.send(formData);
        });
    },
};

export default API;