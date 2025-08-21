
class BasicReceiptParser:
    """Podstawowy parser paragonów jako fallback dla AdaptiveReceiptParser."""
    
    def __init__(self):
        self.name = "basic_parser"
    
    def parse(self, text: str, confidence: float = 0.0) -> dict:
        """
        Podstawowy parsing tekstu paragonu.
        Wyciąga podstawowe informacje bez zaawansowanej logiki.
        """
        lines = text.strip().split('n')
        
        # Podstawowa struktura zwracanych danych
        result = {
            'store_name': self._extract_store_name(lines),
            'total_amount': self._extract_total(lines),
            'date': self._extract_date(lines),
            'items': self._extract_items(lines),
            'parser_used': self.name,
            'confidence': confidence
        }
        
        return result
    
    def _extract_store_name(self, lines: list) -> str:
        """Wyciąga nazwę sklepu z pierwszych linii."""
        for line in lines[:5]:  # Sprawdź pierwsze 5 linii
            if len(line) > 3 and not any(char.isdigit() for char in line):
                return line.strip()
        return "Unknown Store"
    
    def _extract_total(self, lines: list) -> float:
        """Wyciąga kwotę całkowitą."""
        import re
        
        for line in reversed(lines):  # Sprawdź od końca
            # Szukaj wzorca z kwotą (np. "SUMA: 23,45" lub "TOTAL 23.45")
            money_match = re.search(r'(d+[,.]d{2})', line)
            if money_match and ('suma' in line.lower() or 'total' in line.lower()):
                amount_str = money_match.group(1).replace(',', '.')
                return float(amount_str)
        
        return 0.0
    
    def _extract_date(self, lines: list) -> str:
        """Wyciąga datę z paragonu."""
        import re
        
        for line in lines:
            # Wzorce dat: DD-MM-YYYY, DD.MM.YYYY, DD/MM/YYYY
            date_match = re.search(r'(d{2}[-/.]d{2}[-/.]d{4})', line)
            if date_match:
                return date_match.group(1)
        
        return ""
    
    def _extract_items(self, lines: list) -> list:
        """Wyciąga pozycje z paragonu."""
        import re
        items = []
        
        for line in lines:
            # Szukaj linii z ceną (zawiera cyfry i przecinek/kropkę)
            if re.search(r'd+[,.]d{2}', line) and len(line) > 10:
                # Prosta heurystyka: jeśli linia ma cenę i jest odpowiednio długa
                price_match = re.search(r'(d+[,.]d{2})', line)
                if price_match:
                    price = float(price_match.group(1).replace(',', '.'))
                    # Nazwa produktu to część przed ceną
                    name = re.sub(r's*d+[,.]d{2}.*$', '', line).strip()
                    
                    if name and len(name) > 2:  # Filtruj zbyt krótkie nazwy
                        items.append({
                            'name': name,
                            'price': price,
                            'quantity': 1  # Domyślnie 1
                        })
        
        return items
