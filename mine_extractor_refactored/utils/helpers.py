    @staticmethod
    def extract_json_from_text(text: str) -> Optional[str]:
        """
        Extrahiert JSON aus Text mit verschiedenen Fallback-Optionen
        
        Args:
            text: Text mit potentiellem JSON
            
        Returns:
            JSON-String oder None
        """
        if not text:
            return None
        
        # Pattern 1: JSON in Code-Blocks
        for pattern in JSON_PATTERNS:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Pattern 2: Direktes JSON (zwischen erstem { und letztem })
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx + 1].strip()
            if json_str.startswith('{') and json_str.endswith('}'):
                return json_str
        
        # Pattern 3: Mehrere JSON-Objekte - nimm das erste vollständige
        json_objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text)
        for json_obj in json_objects:
            if len(json_obj) > 10:  # Mindestlänge für sinnvolles JSON
                return json_obj
        
        # Pattern 4: Fallback - versuche alles zwischen den ersten Klammern
        brackets_match = re.search(r'(\{.*\})', text, re.DOTALL)
        if brackets_match:
            return brackets_match.group(1)
        
        # Pattern 5: Wenn kein JSON gefunden, erstelle ein einfaches JSON aus dem Text
        # Extrahiere Informationen aus dem Text
        extracted_data = {}
        
        # Suche nach Minenname
        mine_name_match = re.search(r'(?:Mine|Mines?)\s+([A-Za-zÀ-ÿ\s\-\.]+?)(?:\s|$|\.|,|;)', text, re.IGNORECASE)
        if mine_name_match:
            extracted_data["name"] = mine_name_match.group(1).strip()
        
        # Suche nach Standort
        location_match = re.search(r'(?:Standort|Location|Lieu|Site)\s*[:=]\s*([A-Za-zÀ-ÿ\s\-\.]+?)(?:\s|$|\.|,|;)', text, re.IGNORECASE)
        if location_match:
            extracted_data["location"] = location_match.group(1).strip()
        
        # Suche nach Datum
        date_match = re.search(r'(\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}|\d{4}[\/\-\.]\d{1,2}[\/\-\.]\d{1,2})', text)
        if date_match:
            extracted_data["date"] = date_match.group(1)
        
        # Suche nach Produktion
        production_match = re.search(r'(?:Produktion|Production)\s*[:=]\s*([0-9,\.\s]+?)(?:\s|$|\.|,|;)', text, re.IGNORECASE)
        if production_match:
            extracted_data["production"] = production_match.group(1).strip()
        
        # Wenn wir Daten extrahiert haben, erstelle JSON
        if extracted_data:
            return json.dumps(extracted_data, ensure_ascii=False)
        
        return None