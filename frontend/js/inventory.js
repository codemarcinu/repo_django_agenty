/**
 * Inventory module for Agenty frontend
 * Handles inventory management (products, consumption, filtering)
 */

import Utils from './utils.js';
import API from './api.js';
import App from './app.js';

const InventoryModule = {
    // State
    inventoryItems: [],
    filteredItems: [],
    filters: {
        search: '',
        location: 'all',
        expiry: 'all'
    },
    
    // Initialize inventory interface
    init: function() {
        console.log('Initializing inventory module...');
        
        // Initialize event listeners
        this.initEventListeners();
        
        // Load inventory items
        this.loadInventoryItems();
    },
    
    // Initialize event listeners
    initEventListeners: function() {
        // Search input
        const searchInput = document.getElementById('inventory-search');
        if (searchInput) {
            searchInput.addEventListener('input', Utils.debounce(() => {
                this.filters.search = searchInput.value.trim().toLowerCase();
                this.applyFilters();
            }, 300));
        }
        
        // Location filter
        const locationFilter = document.getElementById('location-filter');
        if (locationFilter) {
            locationFilter.addEventListener('change', () => {
                this.filters.location = locationFilter.value;
                this.applyFilters();
            });
        }
        
        // Expiry filter
        const expiryFilter = document.getElementById('expiry-filter');
        if (expiryFilter) {
            expiryFilter.addEventListener('change', () => {
                this.filters.expiry = expiryFilter.value;
                this.applyFilters();
            });
        }
        
        // Add product form
        const addProductForm = document.getElementById('add-product-form');
        if (addProductForm) {
            addProductForm.addEventListener('submit', this.handleAddProduct.bind(this));
        }
    },
    
    // Load inventory items
    loadInventoryItems: async function() {
        const inventoryGrid = document.getElementById('inventory-grid');
        if (!inventoryGrid) return;
        
        // Show loading state
        inventoryGrid.innerHTML = '<div class="loading-indicator"><div class="spinner"></div><span>Ładowanie produktów...</span></div>';
        
        try {
            const response = await API.getInventoryItems();
            
            if (response && response.items && response.items.length > 0) {
                this.inventoryItems = response.items;
                this.filteredItems = [...this.inventoryItems];
                this.renderInventoryItems();
            } else {
                // No items
                inventoryGrid.innerHTML = '<div class="empty-state">Brak produktów w spiżarni.</div>';
            }
        } catch (error) {
            console.error('Error loading inventory items:', error);
            inventoryGrid.innerHTML = '<div class="error-state">Błąd ładowania produktów.</div>';
        }
    },
    
    // Render inventory items
    renderInventoryItems: function() {
        const inventoryGrid = document.getElementById('inventory-grid');
        if (!inventoryGrid) return;
        
        // Clear grid
        inventoryGrid.innerHTML = '';
        
        if (this.filteredItems.length === 0) {
            // No items matching filters
            if (this.hasActiveFilters()) {
                inventoryGrid.innerHTML = '<div class="empty-state">Brak produktów spełniających kryteria filtrowania.</div>';
            } else {
                inventoryGrid.innerHTML = '<div class="empty-state">Brak produktów w spiżarni.</div>';
            }
            return;
        }
        
        // Add items to grid
        this.filteredItems.forEach(item => {
            const card = document.createElement('div');
            card.className = 'product-card';
            card.dataset.id = item.id;
            
            // Calculate expiry status
            const daysUntil = Utils.daysUntilExpiry(item.expiry_date);
            const expiryText = Utils.getExpiryText(item.expiry_date);
            const expiryClass = Utils.getExpiryStatusClass(item.expiry_date);
            
            card.innerHTML = `
                <div class="product-header">
                    <h3 class="product-name">${item.product.name}</h3>
                    <span class="product-expiry-tag ${expiryClass}">${expiryText}</span>
                </div>
                
                <div class="product-details">
                    <div class="product-quantity">
                        <span>Ilość:</span>
                        <span class="quantity-value">${item.quantity_remaining} ${item.unit}</span>
                    </div>
                    
                    <div class="product-location">
                        <i class="fas ${App.getLocationIcon(item.storage_location)}"></i>
                        <span>${App.getLocationName(item.storage_location)}</span>
                    </div>
                    
                    ${item.product.category ? 
                        `<div class="product-category">
                            <i class="fas fa-tag"></i>
                            <span>${item.product.category.name}</span>
                        </div>` : ''}
                </div>
                
                <div class="product-actions">
                    <button class="consume-btn" data-id="${item.id}">
                        <i class="fas fa-utensils"></i> Zużyj
                    </button>
                    
                    <button class="edit-btn" data-id="${item.id}">
                        <i class="fas fa-edit"></i> Edytuj
                    </button>
                </div>
            `;
            
            // Add event listeners
            card.querySelector('.consume-btn').addEventListener('click', () => {
                this.showConsumeModal(item);
            });
            
            card.querySelector('.edit-btn').addEventListener('click', () => {
                this.showEditModal(item);
            });
            
            inventoryGrid.appendChild(card);
        });
    },
    
    // Apply filters to inventory items
    applyFilters: function() {
        // Start with all items
        this.filteredItems = [...this.inventoryItems];
        
        // Apply search filter
        if (this.filters.search) {
            this.filteredItems = this.filteredItems.filter(item => 
                item.product.name.toLowerCase().includes(this.filters.search) ||
                (item.product.category && item.product.category.name.toLowerCase().includes(this.filters.search))
            );
        }
        
        // Apply location filter
        if (this.filters.location !== 'all') {
            this.filteredItems = this.filteredItems.filter(item => 
                item.storage_location === this.filters.location
            );
        }
        
        // Apply expiry filter
        if (this.filters.expiry !== 'all') {
            const today = new Date();
            today.setHours(0, 0, 0, 0);
            
            switch (this.filters.expiry) {
                case 'expired':
                    this.filteredItems = this.filteredItems.filter(item => 
                        item.expiry_date && new Date(item.expiry_date) < today
                    );
                    break;
                    
                case 'today':
                    this.filteredItems = this.filteredItems.filter(item => {
                        if (!item.expiry_date) return false;
                        const expiryDate = new Date(item.expiry_date);
                        expiryDate.setHours(0, 0, 0, 0);
                        return expiryDate.getTime() === today.getTime();
                    });
                    break;
                    
                case 'week':
                    const weekLater = new Date(today);
                    weekLater.setDate(today.getDate() + 7);
                    
                    this.filteredItems = this.filteredItems.filter(item => {
                        if (!item.expiry_date) return false;
                        const expiryDate = new Date(item.expiry_date);
                        return expiryDate >= today && expiryDate <= weekLater;
                    });
                    break;
                    
                case 'month':
                    const monthLater = new Date(today);
                    monthLater.setMonth(today.getMonth() + 1);
                    
                    this.filteredItems = this.filteredItems.filter(item => {
                        if (!item.expiry_date) return false;
                        const expiryDate = new Date(item.expiry_date);
                        return expiryDate >= today && expiryDate <= monthLater;
                    });
                    break;
            }
        }
        
        // Update UI with filtered items
        this.renderInventoryItems();
    },
    
    // Check if any filters are active
    hasActiveFilters: function() {
        return this.filters.search || 
               this.filters.location !== 'all' || 
               this.filters.expiry !== 'all';
    },
    
    // Handle add product form submission
    handleAddProduct: async function(event) {
        event.preventDefault();
        
        // Get form data
        const productName = document.getElementById('product-name').value;
        const productQuantity = parseFloat(document.getElementById('product-quantity').value);
        const productUnit = document.getElementById('product-unit').value;
        const productLocation = document.getElementById('product-location').value;
        const productExpiry = document.getElementById('product-expiry').value;
        
        // Validate form data
        if (!productName || !productQuantity || !productUnit || !productLocation) {
            Utils.showToast('Wypełnij wszystkie wymagane pola.', 'error');
            return;
        }
        
        try {
            const productData = {
                name: productName,
                quantity: productQuantity,
                unit: productUnit,
                storage_location: productLocation,
                expiry_date: productExpiry || null
            };
            
            const response = await API.addInventoryItem(productData);
            
            // Add new item to list
            this.inventoryItems.unshift(response.item);
            
            // Reapply filters
            this.applyFilters();
            
            // Close modal
            this.closeModal('add-product-modal');
            
            // Reset form
            document.getElementById('add-product-form').reset();
            
            // Show success message
            Utils.showToast(`Produkt "${productName}" został dodany.`, 'success');
        } catch (error) {
            console.error('Error adding product:', error);
            Utils.showToast('Błąd dodawania produktu: ' + error.message, 'error');
        }
    },
    
    // Show consume modal
    showConsumeModal: async function(item) {
        // For demo purposes, use simple confirm dialog
        const consumeQuantity = prompt(`Ile ${item.unit} produktu "${item.product.name}" chcesz zużyć? (maksymalnie ${item.quantity_remaining})`, '1');
        
        if (consumeQuantity === null) {
            // User cancelled
            return;
        }
        
        // Parse quantity
        const quantity = parseFloat(consumeQuantity);
        
        // Validate quantity
        if (isNaN(quantity) || quantity <= 0) {
            Utils.showToast('Podaj prawidłową ilość.', 'error');
            return;
        }
        
        if (quantity > item.quantity_remaining) {
            Utils.showToast(`Nie możesz zużyć więcej niż ${item.quantity_remaining} ${item.unit}.`, 'error');
            return;
        }
        
        try {
            await API.consumeInventoryItem(item.id, quantity);
            
            // Update local data
            const itemIndex = this.inventoryItems.findIndex(i => i.id === item.id);
            if (itemIndex !== -1) {
                this.inventoryItems[itemIndex].quantity_remaining -= quantity;
                
                // If quantity is 0, remove item
                if (this.inventoryItems[itemIndex].quantity_remaining <= 0) {
                    this.inventoryItems.splice(itemIndex, 1);
                }
            }
            
            // Reapply filters
            this.applyFilters();
            
            // Show success message
            Utils.showToast(`Zużyto ${quantity} ${item.unit} produktu "${item.product.name}".`, 'success');
        } catch (error) {
            console.error('Error consuming item:', error);
            Utils.showToast('Błąd zużycia produktu: ' + error.message, 'error');
        }
    },
    
    // Show edit modal
    showEditModal: function(item) {
        // For demo purposes, just show toast
        Utils.showToast(`Edycja produktu "${item.product.name}" nie jest zaimplementowana w wersji demo.`, 'info');
        
        // In a real implementation, we would:
        // 1. Create and show a modal with form
        // 2. Fill form with item data
        // 3. Handle form submission
        // 4. Update item via API
        // 5. Update local data and UI
    },
    
    // Close modal helper
    closeModal: function(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.classList.remove('show');
        }
    }
};

// Initialize module when page is loaded
document.addEventListener('DOMContentLoaded', () => {
    // Initialize only if inventory page is active
    if (window.location.hash === '#inventory') {
        InventoryModule.init();
    }
    
    // Listen for hash changes
    window.addEventListener('hashchange', () => {
        if (window.location.hash === '#inventory') {
            InventoryModule.init();
        }
    });
});

// Export for ES6 modules
export default InventoryModule;
