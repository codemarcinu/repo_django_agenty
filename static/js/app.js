/**
 * Main application script for Agenty frontend
 * Handles routing, navigation, and initialization
 */

import Utils from './utils.js';
import API from './api.js';

// Global app state
const App = {
    // Current active page
    currentPage: 'dashboard',
    
    // Session information
    session: {
        activeChatSession: null
    },
    
    // Initialize the application
    init: function() {
        console.log('Initializing Agenty frontend...');
        
        // Set current date in the header
        this.updateCurrentDate();
        
        // Initialize navigation
        this.initNavigation();
        
        // Handle mobile menu toggle
        this.initMobileMenu();
        
        // Initialize page specific content
        this.initPageContent();
        
        // Setup event listeners for quick action buttons
        this.initQuickActions();
        
        // Listen for hash changes
        window.addEventListener('hashchange', this.handleHashChange.bind(this));
        
        // Process initial hash
        this.handleHashChange();
        
        // Initialize WebSocket for real-time updates (if supported)
        this.initWebSocket();
        
        console.log('Agenty frontend initialized');
    },
    
    // Update current date display
    updateCurrentDate: function() {
        const dateDisplay = document.getElementById('current-date');
        if (dateDisplay) {
            const now = new Date();
            dateDisplay.textContent = Utils.formatDate(now, true);
        }
    },
    
    // Initialize navigation
    initNavigation: function() {
        const navItems = document.querySelectorAll('.nav-item');
        
        navItems.forEach(item => {
            item.addEventListener('click', (event) => {
                // Prevent default anchor behavior
                event.preventDefault();
                
                const page = item.dataset.page;
                if (page) {
                    // Update hash (will trigger hashchange event)
                    window.location.hash = page;
                }
            });
        });
    },
    
    // Handle mobile menu toggle
    initMobileMenu: function() {
        const menuToggle = document.getElementById('menu-toggle');
        const sidebar = document.querySelector('.sidebar');
        
        if (menuToggle && sidebar) {
            menuToggle.addEventListener('click', () => {
                sidebar.classList.toggle('expanded');
            });
            
            // Close menu when clicking outside
            document.addEventListener('click', (event) => {
                if (sidebar.classList.contains('expanded') && 
                    !sidebar.contains(event.target) && 
                    event.target !== menuToggle) {
                    sidebar.classList.remove('expanded');
                }
            });
        }
    },
    
    // Initialize quick action buttons
    initQuickActions: function() {
        const actionButtons = document.querySelectorAll('.action-button');
        
        actionButtons.forEach(button => {
            button.addEventListener('click', () => {
                const page = button.dataset.page;
                if (page) {
                    // Navigate to page
                    window.location.hash = page;
                    
                    // Additional actions based on button
                    switch (page) {
                        case 'chat':
                            // Maybe focus the chat input
                            setTimeout(() => {
                                const chatInput = document.getElementById('chat-input');
                                if (chatInput) chatInput.focus();
                            }, 100);
                            break;
                        
                        case 'receipts':
                            // Maybe focus the file upload
                            break;
                            
                        case 'inventory':
                            // Maybe open the add product modal
                            break;
                    }
                }
            });
        });
    },
    
    // Handle hash change for navigation
    handleHashChange: function() {
        // Get hash from URL (remove # symbol)
        let hash = window.location.hash.substring(1);
        
        // Default to dashboard if no hash
        if (!hash) {
            hash = 'dashboard';
            // Update URL without triggering another hashchange
            history.replaceState(null, null, `#${hash}`);
        }
        
        // Navigate to the page
        this.navigateToPage(hash);
    },
    
    // Navigate to a specific page
    navigateToPage: function(page) {
        // Validate page
        const validPages = ['dashboard', 'chat', 'receipts', 'inventory', 'analytics'];
        if (!validPages.includes(page)) {
            page = 'dashboard';
        }
        
        // Update current page
        this.currentPage = page;
        
        // Hide all pages
        document.querySelectorAll('.page').forEach(element => {
            element.classList.remove('active');
        });
        
        // Show current page
        const currentPageElement = document.getElementById(page);
        if (currentPageElement) {
            currentPageElement.classList.add('active');
        }
        
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.page === page) {
                item.classList.add('active');
            }
        });
        
        // Load page-specific content
        this.loadPageContent(page);
        
        // Close mobile sidebar if open
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && sidebar.classList.contains('expanded')) {
            sidebar.classList.remove('expanded');
        }
    },
    
    // Initialize page content
    initPageContent: function() {
        // Load dashboard content (default page)
        this.loadPageContent('dashboard');
        
        // Initialize modals
        this.initModals();
    },
    
    // Load content for a specific page
    loadPageContent: function(page) {
        console.log(`Loading content for page: ${page}`);
        
        switch (page) {
            case 'dashboard':
                this.loadDashboardContent();
                break;
                
            case 'chat':
                // Initialize chat interface
                // This will be handled by chat.js
                break;
                
            case 'receipts':
                // Initialize receipts interface
                // This will be handled by receipts.js
                break;
                
            case 'inventory':
                // Initialize inventory interface
                // This will be handled by inventory.js
                break;
                
            case 'analytics':
                // Initialize analytics interface
                // This will be handled by analytics.js
                break;
        }
    },
    
    // Load dashboard content
    loadDashboardContent: function() {
        // Load dashboard statistics
        this.loadDashboardStatistics();
        
        // Load expiring items
        this.loadExpiringItems();
        
        // Load recent receipts
        this.loadRecentReceipts();
    },
    
    // Load dashboard statistics
    loadDashboardStatistics: async function() {
        try {
            const stats = await API.getInventoryStatistics();
            
            // Update statistics in the UI
            document.getElementById('total-inventory-count').textContent = stats.total_items || 0;
            document.getElementById('expiring-soon-count').textContent = stats.expiring_soon_count || 0;
            document.getElementById('receipts-count').textContent = stats.receipts_count || 0;
            document.getElementById('alerts-count').textContent = (stats.expired_count || 0) + (stats.low_stock_count || 0);
            
        } catch (error) {
            console.error('Error loading dashboard statistics:', error);
            Utils.showToast('Nie udało się załadować statystyk.', 'error');
            
            // Set default values on error
            document.getElementById('total-inventory-count').textContent = '0';
            document.getElementById('expiring-soon-count').textContent = '0';
            document.getElementById('receipts-count').textContent = '0';
            document.getElementById('alerts-count').textContent = '0';
        }
    },
    
    // Load expiring items
    loadExpiringItems: async function() {
        const expiringList = document.getElementById('expiring-items-list');
        if (!expiringList) return;
        
        try {
            const expiringItems = await API.getExpiringItems(7);
            
            // Clear current list
            expiringList.innerHTML = '';
            
            if (!expiringItems || expiringItems.length === 0) {
                expiringList.innerHTML = '<li class="expiring-item">Brak produktów wygasających w najbliższym czasie.</li>';
                return;
            }
            
            // Add items to list
            expiringItems.forEach(item => {
                const li = document.createElement('li');
                li.className = 'expiring-item';
                
                const daysUntil = Utils.daysUntilExpiry(item.expiry_date);
                const expiryText = Utils.getExpiryText(item.expiry_date);
                const statusClass = Utils.getExpiryStatusClass(item.expiry_date);
                
                li.innerHTML = `
                    <div class="expiring-item-header">
                        <span class="item-name">${item.product.name}</span>
                        <span class="expiry-tag ${statusClass}">${expiryText}</span>
                    </div>
                    <div class="expiring-item-details">
                        <span class="item-quantity">${item.quantity_remaining} ${item.unit}</span>
                        <span class="item-location">
                            <i class="fas ${this.getLocationIcon(item.storage_location)}"></i>
                            ${this.getLocationName(item.storage_location)}
                        </span>
                    </div>
                `;
                
                expiringList.appendChild(li);
            });
            
        } catch (error) {
            console.error('Error loading expiring items:', error);
            expiringList.innerHTML = '<li class="expiring-item">Błąd ładowania produktów.</li>';
        }
    },
    
    // Load recent receipts
    loadRecentReceipts: async function() {
        const receiptsList = document.getElementById('recent-receipts-list');
        if (!receiptsList) return;
        
        try {
            const recentReceipts = await API.getRecentReceipts(5);
            
            // Clear current list
            receiptsList.innerHTML = '';
            
            if (!recentReceipts || recentReceipts.length === 0) {
                receiptsList.innerHTML = '<li class="receipt-item">Brak ostatnich paragonów.</li>';
                return;
            }
            
            // Add items to list
            recentReceipts.forEach(receipt => {
                const li = document.createElement('li');
                li.className = 'receipt-item';
                
                li.innerHTML = `
                    <div class="receipt-item-header">
                        <span class="receipt-store">${receipt.store_name}</span>
                        <span class="receipt-total">${Utils.formatCurrency(receipt.total, receipt.currency)}</span>
                    </div>
                    <div class="receipt-item-details">
                        <span class="receipt-date">${Utils.formatDate(receipt.purchased_at, true)}</span>
                        <span class="receipt-items-count">${receipt.line_items_count} produktów</span>
                    </div>
                `;
                
                receiptsList.appendChild(li);
            });
            
        } catch (error) {
            console.error('Error loading recent receipts:', error);
            receiptsList.innerHTML = '<li class="receipt-item">Błąd ładowania paragonów.</li>';
        }
    },
    
    // Initialize WebSocket for real-time updates
    initWebSocket: function() {
        // Check if WebSocket is supported
        if ('WebSocket' in window) {
            try {
                // Connect to WebSocket server
                // this.ws = new WebSocket('ws://localhost:8000/ws/notifications/');
                
                // WebSocket events
                // this.ws.onopen = () => console.log('WebSocket connected');
                // this.ws.onmessage = this.handleWebSocketMessage.bind(this);
                // this.ws.onerror = (error) => console.error('WebSocket error:', error);
                // this.ws.onclose = () => console.log('WebSocket disconnected');
                
                console.log('WebSocket initialization skipped for demo');
            } catch (e) {
                console.error('Error initializing WebSocket:', e);
            }
        } else {
            console.warn('WebSocket is not supported in this browser');
        }
    },
    
    // Handle WebSocket messages
    handleWebSocketMessage: function(event) {
        try {
            // Parse message data
            const data = JSON.parse(event.data);
            
            // Handle different message types
            switch (data.type) {
                case 'receipt_status_update':
                    // Update receipt status in UI
                    this.updateReceiptStatus(data.receipt_id, data.status, data.message);
                    break;
                    
                case 'expiry_alert':
                    // Show expiry alert
                    Utils.showToast(`Produkt "${data.product_name}" kończy się za ${data.days_left} dni.`, 'warning');
                    break;
                    
                case 'inventory_update':
                    // Update inventory in UI
                    this.refreshInventoryIfVisible();
                    break;
                    
                default:
                    console.log('Unhandled WebSocket message type:', data.type);
            }
        } catch (e) {
            console.error('Error handling WebSocket message:', e);
        }
    },
    
    // Update receipt status in UI
    updateReceiptStatus: function(receiptId, status, message) {
        // Update receipt status in receipts table if visible
        const statusCell = document.querySelector(`#receipt-${receiptId} .receipt-status`);
        if (statusCell) {
            // Remove all status classes
            statusCell.classList.remove('pending', 'processing', 'review', 'completed', 'error');
            
            // Add new status class
            statusCell.classList.add(status);
            
            // Update text
            statusCell.textContent = this.getStatusDisplayName(status);
        }
        
        // Update processing status container if visible
        const processingStatus = document.getElementById('receipt-processing-status');
        if (processingStatus && processingStatus.dataset.receiptId === String(receiptId)) {
            const statusText = document.getElementById('receipt-status-text');
            if (statusText) {
                statusText.textContent = message || this.getStatusDisplayName(status);
            }
            
            // Update progress bar
            const progressBar = document.getElementById('receipt-progress-bar');
            if (progressBar) {
                let progress = 0;
                
                switch (status) {
                    case 'pending':
                        progress = 10;
                        break;
                    case 'processing':
                        progress = 50;
                        break;
                    case 'review':
                        progress = 80;
                        break;
                    case 'completed':
                        progress = 100;
                        break;
                    case 'error':
                        progress = 100;
                        break;
                }
                
                progressBar.style.width = `${progress}%`;
            }
            
            // If completed or error, refresh receipts list
            if (status === 'completed' || status === 'error') {
                setTimeout(() => {
                    // Hide processing status
                    processingStatus.style.display = 'none';
                    
                    // Show receipt upload area
                    const uploadArea = document.getElementById('receipt-upload-area');
                    if (uploadArea) {
                        uploadArea.style.display = 'block';
                    }
                    
                    // Refresh receipts list
                    // Call to specific module function
                }, 2000);
            }
        }
        
        // Show toast notification for important status changes
        if (status === 'completed') {
            Utils.showToast('Paragon został pomyślnie przetworzony!', 'success');
        } else if (status === 'error') {
            Utils.showToast('Wystąpił błąd podczas przetwarzania paragonu.', 'error');
        } else if (status === 'review') {
            Utils.showToast('Paragon gotowy do weryfikacji.', 'info');
        }
    },
    
    // Refresh inventory if the inventory page is visible
    refreshInventoryIfVisible: function() {
        if (this.currentPage === 'inventory') {
            // Call to inventory module function to refresh data
            // inventoryModule.loadInventoryItems();
        }
    },
    
    // Initialize modals
    initModals: function() {
        // Add Product Modal
        const addProductModal = document.getElementById('add-product-modal');
        const addProductBtn = document.getElementById('add-product-btn');
        const closeProductModal = document.getElementById('close-product-modal');
        const cancelProductBtn = document.getElementById('cancel-product-btn');
        
        if (addProductModal && addProductBtn) {
            // Open modal
            addProductBtn.addEventListener('click', () => {
                addProductModal.classList.add('show');
            });
            
            // Close modal
            const closeModal = () => {
                addProductModal.classList.remove('show');
            };
            
            if (closeProductModal) {
                closeProductModal.addEventListener('click', closeModal);
            }
            
            if (cancelProductBtn) {
                cancelProductBtn.addEventListener('click', closeModal);
            }
            
            // Close modal when clicking outside
            window.addEventListener('click', (event) => {
                if (event.target === addProductModal) {
                    closeModal();
                }
            });
            
            // Handle form submission
            const addProductForm = document.getElementById('add-product-form');
            if (addProductForm) {
                addProductForm.addEventListener('submit', (event) => {
                    event.preventDefault();
                    
                    // Get form data
                    const productName = document.getElementById('product-name').value;
                    const productQuantity = document.getElementById('product-quantity').value;
                    const productUnit = document.getElementById('product-unit').value;
                    const productLocation = document.getElementById('product-location').value;
                    const productExpiry = document.getElementById('product-expiry').value;
                    
                    // Validate form data
                    if (!productName || !productQuantity || !productUnit || !productLocation) {
                        Utils.showToast('Wypełnij wszystkie wymagane pola.', 'error');
                        return;
                    }
                    
                    // Create product data
                    const productData = {
                        name: productName,
                        quantity: parseFloat(productQuantity),
                        unit: productUnit,
                        storage_location: productLocation,
                        expiry_date: productExpiry || null
                    };
                    
                    // Call to inventory module function to add product
                    // inventoryModule.addProduct(productData);
                    
                    // For demo purposes, show success message
                    Utils.showToast(`Produkt "${productName}" został dodany.`, 'success');
                    
                    // Close modal
                    closeModal();
                    
                    // Reset form
                    addProductForm.reset();
                });
            }
        }
    },
    
    // Helper function to get location icon
    getLocationIcon: function(location) {
        switch (location) {
            case 'fridge':
                return 'fa-snowflake';
            case 'freezer':
                return 'fa-icicles';
            case 'pantry':
                return 'fa-box';
            case 'cabinet':
                return 'fa-archive';
            default:
                return 'fa-warehouse';
        }
    },
    
    // Helper function to get location name
    getLocationName: function(location) {
        switch (location) {
            case 'fridge':
                return 'Lodówka';
            case 'freezer':
                return 'Zamrażarka';
            case 'pantry':
                return 'Spiżarnia';
            case 'cabinet':
                return 'Szafka';
            default:
                return 'Inne';
        }
    },
    
    // Helper function to get status display name
    getStatusDisplayName: function(status) {
        switch (status) {
            case 'pending':
                return 'Oczekuje';
            case 'processing':
                return 'Przetwarzanie';
            case 'review':
                return 'Do weryfikacji';
            case 'completed':
                return 'Zakończono';
            case 'error':
                return 'Błąd';
            default:
                return status;
        }
    }
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export App for ES6 modules
export default App;
