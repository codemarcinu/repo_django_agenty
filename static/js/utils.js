/**
 * Utility functions for Agenty frontend
 */

const Utils = {
    /**
     * Format date to display format
     * @param {string|Date} date - Date to format
     * @param {boolean} includeTime - Whether to include time
     * @returns {string} Formatted date string
     */
    formatDate: function(date, includeTime = false) {
        if (!date) return '';
        
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        
        const options = {
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        };
        
        if (includeTime) {
            options.hour = '2-digit';
            options.minute = '2-digit';
        }
        
        try {
            return dateObj.toLocaleDateString('pl-PL', options);
        } catch (e) {
            console.error('Error formatting date:', e);
            return String(date);
        }
    },
    
    /**
     * Format currency amount
     * @param {number} amount - Amount to format
     * @param {string} currency - Currency code (default: PLN)
     * @returns {string} Formatted currency string
     */
    formatCurrency: function(amount, currency = 'PLN') {
        if (amount === null || amount === undefined) return '';
        
        try {
            return new Intl.NumberFormat('pl-PL', {
                style: 'currency',
                currency: currency
            }).format(amount);
        } catch (e) {
            console.error('Error formatting currency:', e);
            return `${amount} ${currency}`;
        }
    },
    
    /**
     * Create a toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of toast (success, error, warning, info)
     * @param {number} duration - Duration in milliseconds
     */
    showToast: function(message, type = 'info', duration = 3000) {
        const toastContainer = document.getElementById('toast-container');
        
        if (!toastContainer) {
            console.error('Toast container not found');
            return;
        }
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const toastHeader = document.createElement('div');
        toastHeader.className = 'toast-header';
        
        const toastTitle = document.createElement('span');
        toastTitle.className = 'toast-title';
        
        switch (type) {
            case 'success':
                toastTitle.textContent = 'Sukces!';
                break;
            case 'error':
                toastTitle.textContent = 'Błąd!';
                break;
            case 'warning':
                toastTitle.textContent = 'Uwaga!';
                break;
            default:
                toastTitle.textContent = 'Informacja';
        }
        
        const closeButton = document.createElement('button');
        closeButton.className = 'close-btn';
        closeButton.innerHTML = '&times;';
        closeButton.addEventListener('click', () => {
            toast.remove();
        });
        
        toastHeader.appendChild(toastTitle);
        toastHeader.appendChild(closeButton);
        
        const toastBody = document.createElement('div');
        toastBody.className = 'toast-body';
        toastBody.textContent = message;
        
        toast.appendChild(toastHeader);
        toast.appendChild(toastBody);
        
        toastContainer.appendChild(toast);
        
        // Auto-remove toast after duration
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, duration);
    },
    
    /**
     * Truncate text to a specific length
     * @param {string} text - Text to truncate
     * @param {number} length - Maximum length
     * @returns {string} Truncated text
     */
    truncateText: function(text, length = 50) {
        if (!text) return '';
        
        return text.length > length
            ? text.substring(0, length) + '...'
            : text;
    },
    
    /**
     * Format relative time (e.g., "2 days ago")
     * @param {string|Date} date - Date to format
     * @returns {string} Relative time string
     */
    timeAgo: function(date) {
        if (!date) return '';
        
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        const now = new Date();
        const diffMs = now - dateObj;
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);
        
        if (diffSec < 60) {
            return 'przed chwilą';
        } else if (diffMin < 60) {
            return `${diffMin} ${this.pluralize(diffMin, 'minuta', 'minuty', 'minut')} temu`;
        } else if (diffHour < 24) {
            return `${diffHour} ${this.pluralize(diffHour, 'godzina', 'godziny', 'godzin')} temu`;
        } else if (diffDay < 7) {
            return `${diffDay} ${this.pluralize(diffDay, 'dzień', 'dni', 'dni')} temu`;
        } else {
            return this.formatDate(dateObj);
        }
    },
    
    /**
     * Helper for Polish pluralization
     * @param {number} count - Count
     * @param {string} singular - Singular form
     * @param {string} plural - Plural form for 2-4
     * @param {string} plural2 - Plural form for 5+
     * @returns {string} Correct plural form
     */
    pluralize: function(count, singular, plural, plural2) {
        if (count === 1) {
            return singular;
        }
        
        if (count % 10 >= 2 && count % 10 <= 4 && (count % 100 < 10 || count % 100 >= 20)) {
            return plural;
        }
        
        return plural2;
    },
    
    /**
     * Format file size
     * @param {number} bytes - File size in bytes
     * @returns {string} Formatted file size
     */
    formatFileSize: function(bytes) {
        if (bytes === 0) return '0 B';
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    /**
     * Format date for input[type="date"]
     * @param {string|Date} date - Date to format
     * @returns {string} Formatted date string (YYYY-MM-DD)
     */
    formatDateForInput: function(date) {
        if (!date) return '';
        
        const dateObj = typeof date === 'string' ? new Date(date) : date;
        
        const year = dateObj.getFullYear();
        const month = String(dateObj.getMonth() + 1).padStart(2, '0');
        const day = String(dateObj.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    },
    
    /**
     * Debounce function to limit function calls
     * @param {Function} func - Function to debounce
     * @param {number} wait - Wait time in milliseconds
     * @returns {Function} Debounced function
     */
    debounce: function(func, wait = 300) {
        let timeout;
        
        return function(...args) {
            const context = this;
            
            clearTimeout(timeout);
            
            timeout = setTimeout(() => {
                func.apply(context, args);
            }, wait);
        };
    },
    
    /**
     * Calculate days until expiry date
     * @param {string|Date} expiryDate - Expiry date
     * @returns {number} Days until expiry (negative if expired)
     */
    daysUntilExpiry: function(expiryDate) {
        if (!expiryDate) return null;
        
        const expiry = typeof expiryDate === 'string' ? new Date(expiryDate) : expiryDate;
        const today = new Date();
        
        // Reset time to compare dates only
        today.setHours(0, 0, 0, 0);
        expiry.setHours(0, 0, 0, 0);
        
        const diffTime = expiry - today;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        return diffDays;
    },
    
    /**
     * Get expiry status class
     * @param {string|Date} expiryDate - Expiry date
     * @returns {string} CSS class for expiry status
     */
    getExpiryStatusClass: function(expiryDate) {
        const days = this.daysUntilExpiry(expiryDate);
        
        if (days === null) return '';
        
        if (days < 0) {
            return 'expiry-expired';
        } else if (days <= 3) {
            return 'expiry-warning';
        } else {
            return 'expiry-good';
        }
    },
    
    /**
     * Get human-readable expiry text
     * @param {string|Date} expiryDate - Expiry date
     * @returns {string} Human-readable expiry text
     */
    getExpiryText: function(expiryDate) {
        const days = this.daysUntilExpiry(expiryDate);
        
        if (days === null) return 'Brak daty ważności';
        
        if (days < 0) {
            return `Przeterminowane (${Math.abs(days)} dni temu)`;
        } else if (days === 0) {
            return 'Dziś upływa termin ważności';
        } else if (days === 1) {
            return 'Jutro upływa termin ważności';
        } else {
            return `Ważne przez ${days} ${this.pluralize(days, 'dzień', 'dni', 'dni')}`;
        }
    },
    
    /**
     * Generate a UUID (v4)
     * @returns {string} UUID
     */
    generateUUID: function() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            const r = Math.random() * 16 | 0;
            const v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    },
    
    /**
     * Deep clone an object
     * @param {Object} obj - Object to clone
     * @returns {Object} Cloned object
     */
    deepClone: function(obj) {
        return JSON.parse(JSON.stringify(obj));
    },
    
    /**
     * Sanitize HTML string to prevent XSS
     * @param {string} html - HTML string to sanitize
     * @returns {string} Sanitized HTML
     */
    sanitizeHTML: function(html) {
        const div = document.createElement('div');
        div.textContent = html;
        return div.innerHTML;
    }
};

// Export Utils for ES6 modules
export default Utils;
