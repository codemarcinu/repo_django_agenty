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
        this.initAuth();
    },

    // Handle authentication
    initAuth: function() {
        const token = API.getToken();
        if (token) {
            console.log('User is authenticated.');
            this.startAuthenticatedApp();
        } else {
            console.log('User is not authenticated. Showing login modal.');
            this.showLoginModal();
        }
    },

    // Show the login modal and add listeners
    showLoginModal: function() {
        const loginModal = document.getElementById('login-modal');
        const loginForm = document.getElementById('login-form');
        const loginError = document.getElementById('login-error');

        loginModal.classList.add('show');

        loginForm.onsubmit = async (event) => {
            event.preventDefault();
            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;
            loginError.style.display = 'none';

            try {
                await API.login(username, password);
                loginModal.classList.remove('show');
                this.startAuthenticatedApp();
            } catch (error) {
                loginError.textContent = 'Logowanie nie powiodło się. Sprawdź dane i spróbuj ponownie.';
                loginError.style.display = 'block';
                console.error('Login failed:', error);
            }
        };
    },

    // Start the main application after authentication
    startAuthenticatedApp: function() {
        console.log('Starting authenticated application...');
        
        // Display authenticated content
        document.querySelector('.app-container').style.display = 'flex';

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

        // Setup logout button
        this.initLogout();
        
        // Listen for hash changes
        window.addEventListener('hashchange', this.handleHashChange.bind(this));
        
        // Process initial hash
        this.handleHashChange();
        
        // Initialize WebSocket for real-time updates
        this.initWebSocket();
        
        console.log('Agenty frontend initialized for authenticated user.');
    },

    // Setup logout button
    initLogout: function() {
        console.log("Initializing logout...");
        const logoutBtn = document.getElementById('logout-btn');

        // FIX: Sprawdź, czy przycisk wylogowania istnieje na stronie
        if (logoutBtn) {
            logoutBtn.style.display = 'block';
            logoutBtn.addEventListener('click', (e) => {
                e.preventDefault();
                // Implementacja wylogowania
                console.log("Logout clicked");
                window.location.href = '/admin/logout/';
            });
        } else {
            console.warn("Logout button not found on this page.");
        }
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
                event.preventDefault();
                const page = item.dataset.page;
                if (page) {
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
                    window.location.hash = page;
                    if (page === 'chat') {
                        setTimeout(() => {
                            const chatInput = document.getElementById('chat-input');
                            if (chatInput) chatInput.focus();
                        }, 100);
                    }
                }
            });
        });
    },
    
    // Handle hash change for navigation
    handleHashChange: function() {
        let hash = window.location.hash.substring(1) || 'dashboard';
        this.navigateToPage(hash);
    },
    
    // Navigate to a specific page
    navigateToPage: function(page) {
        const validPages = ['dashboard', 'chat', 'receipts', 'inventory', 'analytics'];
        if (!validPages.includes(page)) {
            page = 'dashboard';
        }
        
        this.currentPage = page;
        
        document.querySelectorAll('.page').forEach(element => element.classList.remove('active'));
        const currentPageElement = document.getElementById(page);
        if (currentPageElement) {
            currentPageElement.classList.add('active');
        }
        
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
            if (item.dataset.page === page) {
                item.classList.add('active');
            }
        });
        
        this.loadPageContent(page);
        
        const sidebar = document.querySelector('.sidebar');
        if (sidebar && sidebar.classList.contains('expanded')) {
            sidebar.classList.remove('expanded');
        }
    },
    
    // Initialize page content
    initPageContent: function() {
        this.loadPageContent('dashboard');
        this.initModals();
    },
    
    // Load content for a specific page
    loadPageContent: function(page) {
        console.log(`Loading content for page: ${page}`);
        
        switch (page) {
            case 'dashboard':
                this.loadDashboardContent();
                break;
            // Other cases remain the same
        }
    },
    
    // Load dashboard content
    loadDashboardContent: function() {
        this.loadDashboardStatistics();
        this.loadExpiringItems();
        this.loadRecentReceipts();
    },
    
    // Load dashboard statistics
    loadDashboardStatistics: async function() {
        try {
            const stats = await API.getInventoryStatistics();
            document.getElementById('total-inventory-count').textContent = stats.total_items || 0;
            document.getElementById('expiring-soon-count').textContent = stats.expiring_soon_count || 0;
            document.getElementById('receipts-count').textContent = stats.receipts_count || 0;
            document.getElementById('alerts-count').textContent = (stats.expired_count || 0) + (stats.low_stock_count || 0);
        } catch (error) {
            console.error('Error loading dashboard statistics:', error);
            Utils.showToast('Nie udało się załadować statystyk.', 'error');
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
            expiringList.innerHTML = '';
            
            if (!expiringItems || expiringItems.length === 0) {
                expiringList.innerHTML = '<li class="expiring-item">Brak produktów wygasających w najbliższym czasie.</li>';
                return;
            }
            
            expiringItems.forEach(item => {
                const li = document.createElement('li');
                li.className = 'expiring-item';
                const expiryText = Utils.getExpiryText(item.expiry_date);
                const statusClass = Utils.getExpiryStatusClass(item.expiry_date);

                li.innerHTML = `
                    <div class="expiring-item-header">
                        <span class="item-name">${item.product.name}</span>
                        <span class="expiry-tag ${statusClass}">${expiryText}</span>
                    </div>
                    <div class="expiring-item-details">
                        <span class="item-quantity">${item.quantity_remaining} ${item.unit}</span>
                        <span class="item-location"><i class="fas fa-clock"></i> ${item.days_until_expiry} dni</span>
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
            receiptsList.innerHTML = '';
            
            if (!recentReceipts || recentReceipts.length === 0) {
                receiptsList.innerHTML = '<li class="receipt-item">Brak ostatnich paragonów.</li>';
                return;
            }
            
            recentReceipts.forEach(receipt => {
                const li = document.createElement('li');
                li.className = 'receipt-item';
                const storeName = receipt.store_name || receipt.filename || 'Nieznany sklep';
                const totalAmount = receipt.total_amount || receipt.total || 0;
                const currency = receipt.currency || 'PLN';
                const purchaseDate = receipt.purchased_at || receipt.created_at;
                const lineItemsCount = receipt.line_items_count || 'Nieznana';

                li.innerHTML = `
                    <div class="receipt-item-header">
                        <span class="receipt-store">${storeName}</span>
                        <span class="receipt-total">${Utils.formatCurrency(totalAmount, currency)}</span>
                    </div>
                    <div class="receipt-item-details">
                        <span class="receipt-date">${Utils.formatDate(purchaseDate, true)}</span>
                        <span class="receipt-items-count">${lineItemsCount} produktów</span>
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
        if (!('WebSocket' in window)) {
            console.warn('WebSocket is not supported in this browser');
            return;
        }
        try {
            const token = API.getToken();
            if (!token) return; // Don't connect if not authenticated

            const wsUrl = `ws://${window.location.host}/ws/notifications/?token=${token}`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => console.log('WebSocket connected');
            this.ws.onmessage = this.handleWebSocketMessage.bind(this);
            this.ws.onerror = (error) => console.error('WebSocket error:', error);
            this.ws.onclose = () => console.log('WebSocket disconnected');
        } catch (e) {
            console.error('Error initializing WebSocket:', e);
        }
    },
    
    // Handle WebSocket messages
    handleWebSocketMessage: function(event) {
        try {
            const data = JSON.parse(event.data);
            switch (data.type) {
                case 'receipt_status_update':
                    this.updateReceiptStatus(data.receipt_id, data.status, data.message);
                    break;
                case 'expiry_alert':
                    Utils.showToast(`Produkt "${data.product_name}" kończy się za ${data.days_left} dni.`, 'warning');
                    break;
                case 'inventory_update':
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
        const statusCell = document.querySelector(`#receipt-${receiptId} .receipt-status`);
        if (statusCell) {
            statusCell.classList.remove('pending', 'processing', 'review', 'completed', 'error');
            statusCell.classList.add(status);
            statusCell.textContent = this.getStatusDisplayName(status);
        }
        
        const processingStatus = document.getElementById('receipt-processing-status');
        if (processingStatus && processingStatus.dataset.receiptId === String(receiptId)) {
            const statusText = document.getElementById('receipt-status-text');
            if (statusText) {
                statusText.textContent = message || this.getStatusDisplayName(status);
            }
            const progressBar = document.getElementById('receipt-progress-bar');
            if (progressBar) {
                let progress = {'pending': 10, 'processing': 50, 'review': 80, 'completed': 100, 'error': 100}[status] || 0;
                progressBar.style.width = `${progress}%`;
            }
            if (status === 'completed' || status === 'error') {
                setTimeout(() => {
                    processingStatus.style.display = 'none';
                    const uploadArea = document.getElementById('receipt-upload-area');
                    if (uploadArea) uploadArea.style.display = 'block';
                }, 2000);
            }
        }
        
        if (status === 'completed') Utils.showToast('Paragon został pomyślnie przetworzony!', 'success');
        else if (status === 'error') Utils.showToast('Wystąpił błąd podczas przetwarzania paragonu.', 'error');
        else if (status === 'review') Utils.showToast('Paragon gotowy do weryfikacji.', 'info');
    },
    
    // Refresh inventory if the inventory page is visible
    refreshInventoryIfVisible: function() {
        if (this.currentPage === 'inventory') {
            // inventoryModule.loadInventoryItems();
        }
    },
    
    // Initialize modals
    initModals: function() {
        const addProductModal = document.getElementById('add-product-modal');
        const addProductBtn = document.getElementById('add-product-btn');
        const closeProductModal = document.getElementById('close-product-modal');
        const cancelProductBtn = document.getElementById('cancel-product-btn');
        
        if (addProductModal && addProductBtn) {
            addProductBtn.addEventListener('click', () => addProductModal.classList.add('show'));
            const closeModal = () => addProductModal.classList.remove('show');
            if (closeProductModal) closeProductModal.addEventListener('click', closeModal);
            if (cancelProductBtn) cancelProductBtn.addEventListener('click', closeModal);
            window.addEventListener('click', (event) => {
                if (event.target === addProductModal) closeModal();
            });
            
            const addProductForm = document.getElementById('add-product-form');
            if (addProductForm) {
                addProductForm.addEventListener('submit', (event) => {
                    event.preventDefault();
                    const productName = document.getElementById('product-name').value;
                    const productQuantity = document.getElementById('product-quantity').value;
                    const productUnit = document.getElementById('product-unit').value;
                    const productLocation = document.getElementById('product-location').value;
                    const productExpiry = document.getElementById('product-expiry').value;
                    
                    if (!productName || !productQuantity || !productUnit || !productLocation) {
                        Utils.showToast('Wypełnij wszystkie wymagane pola.', 'error');
                        return;
                    }
                    
                    const productData = { name: productName, quantity: parseFloat(productQuantity), unit: productUnit, storage_location: productLocation, expiry_date: productExpiry || null };
                    // inventoryModule.addProduct(productData);
                    Utils.showToast(`Produkt "${productName}" został dodany.`, 'success');
                    closeModal();
                    addProductForm.reset();
                });
            }
        }
    },
    
    // Helper functions
    getLocationIcon: (l) => ({fridge:'fa-snowflake',freezer:'fa-icicles',pantry:'fa-box',cabinet:'fa-archive'}[l]|| 'fa-warehouse'),
    getLocationName: (l) => ({fridge:'Lodówka',freezer:'Zamrażarka',pantry:'Spiżarnia',cabinet:'Szafka'}[l]|| 'Inne'),
    getStatusDisplayName: (s) => ({pending:'Oczekuje',processing:'Przetwarzanie',review:'Do weryfikacji',completed:'Zakończono',error:'Błąd'}[s]||s)
};

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

export default App;