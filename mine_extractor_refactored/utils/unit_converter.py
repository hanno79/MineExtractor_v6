"""
Einheiten-Konvertierung für Mine-Daten
Normalisiert verschiedene Einheiten auf Standardformate
"""

import re
from typing import Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..utils.logger import MineExtractorLogger


@dataclass
class ConversionResult:
    """Ergebnis einer Einheiten-Konvertierung"""
    value: Optional[float] = None
    unit: str = ""
    original_text: str = ""
    confidence: float = 0.0
    error_message: str = ""
    
    def is_valid(self) -> bool:
        """Prüft ob Konvertierung erfolgreich war"""
        return self.value is not None and self.unit and not self.error_message


class UnitConverter:
    """Konvertiert verschiedene Einheiten in Standardformate"""
    
    def __init__(self, logger: Optional[MineExtractorLogger] = None):
        self.logger = logger or MineExtractorLogger("UnitConverter")
        
        # Fördermengen-Einheiten (Standard: t/Jahr)
        self.production_units = {
            # Tonnen
            't/j': 1.0,
            't/jahr': 1.0,
            't/a': 1.0,
            't/year': 1.0,
            'tonnes/j': 1.0,
            'tonnes/jahr': 1.0,
            'tonnes/a': 1.0,
            'tonnes/year': 1.0,
            
            # Megatonnen
            'mt/j': 1000000.0,
            'mt/jahr': 1000000.0,
            'mt/a': 1000000.0,
            'mt/year': 1000000.0,
            'million tonnes/j': 1000000.0,
            'million tonnes/jahr': 1000000.0,
            'million tonnes/a': 1000000.0,
            'million tonnes/year': 1000000.0,
            
            # Unzen (Gold)
            'oz/j': 31.1035,  # 1 oz = 31.1035 g
            'oz/jahr': 31.1035,
            'oz/a': 31.1035,
            'oz/year': 31.1035,
            'ounces/j': 31.1035,
            'ounces/jahr': 31.1035,
            'ounces/a': 31.1035,
            'ounces/year': 31.1035,
            
            # Kilogramm
            'kg/j': 0.001,
            'kg/jahr': 0.001,
            'kg/a': 0.001,
            'kg/year': 0.001,
            
            # Gramm
            'g/j': 0.000001,
            'g/jahr': 0.000001,
            'g/a': 0.000001,
            'g/year': 0.000001,
        }
        
        # Flächen-Einheiten (Standard: km²)
        self.area_units = {
            # Quadratkilometer
            'km²': 1.0,
            'km2': 1.0,
            'qkm': 1.0,
            'sq km': 1.0,
            'square km': 1.0,
            
            # Hektar
            'ha': 0.01,  # 1 ha = 0.01 km²
            'hectares': 0.01,
            'hectare': 0.01,
            
            # Quadratmeter
            'm²': 0.000001,  # 1 m² = 0.000001 km²
            'm2': 0.000001,
            'sq m': 0.000001,
            'square m': 0.000001,
            
            # Quadratfuß
            'ft²': 0.000000092903,  # 1 ft² = 0.000000092903 km²
            'ft2': 0.000000092903,
            'sq ft': 0.000000092903,
            'square ft': 0.000000092903,
        }
        
        # Konvertierungsfaktoren für verschiedene Ziel-Einheiten
        self.unit_conversion_factors = {
            'km²': 1.0,
            'ha': 100.0,  # 1 km² = 100 ha
        }
    
    def normalize_production_rate(self, text: str) -> ConversionResult:
        """
        Normalisiert Fördermengen auf t/Jahr
        
        Args:
            text: Text mit Fördermenge (z.B. "2,4 Mt/Jahr; >400 000 oz Au")
            
        Returns:
            ConversionResult mit normalisierter Menge
        """
        if not text or not text.strip():
            return ConversionResult(error_message="Leerer Text")
        
        result = ConversionResult(original_text=text)
        
        # Suche nach Zahlen und Einheiten
        patterns = [
            # Standard: Zahl + Einheit
            r'(\d+(?:[.,]\d+)?)\s*([a-zA-Z²]+/[a-zA-Z]+)',
            # Mit Präfixen: >, <, ~, ≈
            r'([><~≈])\s*(\d+(?:[.,]\d+)?)\s*([a-zA-Z²]+/[a-zA-Z]+)',
            # Mit Tausendertrennzeichen
            r'(\d+(?:\s\d{3})*(?:[.,]\d+)?)\s*([a-zA-Z²]+/[a-zA-Z]+)',
        ]
        
        best_match = None
        best_confidence = 0.0
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    if len(match.groups()) == 2:
                        # Standard-Pattern
                        value_str = match.group(1).replace(',', '.')
                        unit = match.group(2).lower()
                        prefix = ""
                    else:
                        # Pattern mit Präfix
                        prefix = match.group(1)
                        value_str = match.group(2).replace(',', '.')
                        unit = match.group(3).lower()
                    
                    # Konvertiere Wert
                    value = float(value_str)
                    
                    # Finde Konvertierungsfaktor
                    conversion_factor = None
                    for unit_pattern, factor in self.production_units.items():
                        if unit_pattern.lower() in unit:
                            conversion_factor = factor
                            break
                    
                    if conversion_factor is None:
                        continue
                    
                    # Berechne normalisierten Wert
                    normalized_value = value * conversion_factor
                    
                    # Bewerte Konfidenz
                    confidence = 0.8  # Basis-Konfidenz
                    if prefix in ['>', '<', '~', '≈']:
                        confidence *= 0.9  # Präfix reduziert Konfidenz
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            'value': normalized_value,
                            'unit': 't/Jahr',
                            'prefix': prefix,
                            'original_value': value,
                            'original_unit': unit
                        }
                
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Fehler bei Konvertierung: {e}")
                    continue
        
        if best_match:
            result.value = best_match['value']
            result.unit = best_match['unit']
            result.confidence = best_confidence
            
            # Erstelle formatierte Ausgabe
            if best_match['prefix']:
                result.original_text = f"{best_match['prefix']}{best_match['original_value']:.1f} {best_match['original_unit']} → {best_match['value']:.1f} t/Jahr"
            else:
                result.original_text = f"{best_match['original_value']:.1f} {best_match['original_unit']} → {best_match['value']:.1f} t/Jahr"
        else:
            result.error_message = "Keine gültige Fördermenge gefunden"
        
        return result
    
    def normalize_area(self, text: str, target_unit: str = "km²") -> ConversionResult:
        """
        Normalisiert Flächenangaben auf gewünschte Einheit
        
        Args:
            text: Text mit Flächenangabe (z.B. "70,9 ha")
            target_unit: Ziel-Einheit ("km²" oder "ha")
            
        Returns:
            ConversionResult mit normalisierter Fläche
        """
        if not text or not text.strip():
            return ConversionResult(error_message="Leerer Text")
        
        result = ConversionResult(original_text=text)
        
        # Suche nach Zahlen und Flächeneinheiten
        patterns = [
            r'(\d+(?:[.,]\d+)?)\s*([a-zA-Z²]+)',
            r'(\d+(?:\s\d{3})*(?:[.,]\d+)?)\s*([a-zA-Z²]+)',
            r'(\d+(?:\s\d{3})*(?:[.,]\d+)?)\s*([a-zA-Z²]+)',  # Tausendertrennzeichen
        ]
        
        best_match = None
        best_confidence = 0.0
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    value_str = match.group(1).replace(',', '.').replace(' ', '')
                    unit = match.group(2).lower()
                    
                    # Konvertiere Wert
                    value = float(value_str)
                    
                    # Finde Konvertierungsfaktor
                    conversion_factor = None
                    for unit_pattern, factor in self.area_units.items():
                        if unit_pattern.lower() in unit:
                            conversion_factor = factor
                            break
                    
                    if conversion_factor is None:
                        continue
                    
                    # Berechne normalisierten Wert (immer in km²)
                    normalized_value_km2 = value * conversion_factor
                    
                    # Konvertiere zu Ziel-Einheit
                    target_factor = self.unit_conversion_factors.get(target_unit, 1.0)
                    normalized_value = normalized_value_km2 * target_factor
                    
                    # Bewerte Konfidenz
                    confidence = 0.9
                    
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_match = {
                            'value': normalized_value,
                            'unit': target_unit,
                            'original_value': value,
                            'original_unit': unit
                        }
                
                except (ValueError, TypeError) as e:
                    self.logger.debug(f"Fehler bei Flächenkonvertierung: {e}")
                    continue
        
        if best_match:
            result.value = best_match['value']
            result.unit = best_match['unit']
            result.confidence = best_confidence
            result.original_text = f"{best_match['original_value']:.1f} {best_match['original_unit']} → {best_match['value']:.4f} {target_unit}"
        else:
            result.error_message = "Keine gültige Flächenangabe gefunden"
        
        return result
    
    def normalize_coordinates(self, text: str) -> ConversionResult:
        """
        Normalisiert Koordinaten zu Lat/Long (Dezimalformat)
        
        Args:
            text: Text mit Koordinaten (z.B. "426542; -77.42", "UTM E=426 542 / N=5 839 397")
            
        Returns:
            ConversionResult mit Lat/Long-Koordinaten
        """
        result = ConversionResult(original_text=text)
        
        if not text or not text.strip():
            result.error_message = "Leerer Text"
            return result
        
        # Spezielle Behandlung für das Format "426542; -77.42" (UTM + Dezimal gemischt)
        mixed_pattern = r'(\d{6})\s*;\s*([+-]?\d+(?:\.\d+)?)'
        mixed_match = re.search(mixed_pattern, text)
        if mixed_match:
            try:
                first_val = mixed_match.group(1)
                second_val = mixed_match.group(2)
                
                # Erste Zahl ist UTM Easting (6-stellig)
                if len(first_val) == 6 and first_val.isdigit():
                    easting = int(first_val)
                    
                    # Zweite Zahl könnte UTM Northing oder Dezimal-Koordinate sein
                    if len(second_val.replace('.', '').replace('-', '')) >= 6:
                        # Wahrscheinlich UTM Northing - hier müssten wir UTM zu Lat/Long konvertieren
                        # Für jetzt setzen wir auf 0, da wir keine UTM-Konvertierung implementiert haben
                        lat = 0.0
                        lon = 0.0
                        result.confidence = 0.3
                        result.original_text = f"UTM {easting}E {second_val}N → Lat/Long (Konvertierung nicht implementiert)"
                    else:
                        # Wahrscheinlich Dezimal-Koordinate (Longitude)
                        lon = float(second_val)
                        # Wir haben nur eine Koordinate, setzen Latitude auf 0
                        lat = 0.0
                        result.confidence = 0.7
                        result.original_text = f"UTM Easting {easting} + Longitude {lon} → Lat/Long"
                    
                    result.value = f"{lat:.6f}, {lon:.6f}"
                    result.unit = "Lat/Long"
                    return result
            except (ValueError, TypeError):
                pass
        
        # UTM-Patterns (konvertiere zu Lat/Long)
        utm_patterns = [
            r'UTM\s*E\s*=\s*(\d+(?:\s\d{3})*)\s*/\s*N\s*=\s*(\d+(?:\s\d{3})*)',
            r'(\d{6})\s*;\s*(\d{7})',  # 426542; 5839397
            r'E\s*(\d+(?:\s\d{3})*)\s*N\s*(\d+(?:\s\d{3})*)',
        ]
        
        for pattern in utm_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 2:
                        first_val = match.group(1).replace(' ', '')
                        second_val = match.group(2).replace(' ', '')
                        
                        # Prüfe ob es sich um UTM-Koordinaten handelt (6-7 stellige Zahlen)
                        if len(first_val) >= 6 and len(second_val) >= 6:
                            easting = int(first_val)
                            northing = int(second_val)
                            
                            # Hier müssten wir UTM zu Lat/Long konvertieren
                            # Für jetzt setzen wir auf 0, da wir keine UTM-Konvertierung implementiert haben
                            lat = 0.0
                            lon = 0.0
                            
                            result.value = f"{lat:.6f}, {lon:.6f}"
                            result.unit = "Lat/Long"
                            result.confidence = 0.3
                            result.original_text = f"UTM {easting}E {northing}N → Lat/Long (Konvertierung nicht implementiert)"
                            return result
                except (ValueError, TypeError):
                    continue
        
        # Lat/Long Patterns (bereits in Dezimalformat)
        lat_long_patterns = [
            r'(\d+)°(\d+)\'(\d+(?:\.\d+)?)"\s*([NS])\s*/\s*(\d+)°(\d+)\'(\d+(?:\.\d+)?)"\s*([EW])',
            r'([+-]?\d+(?:\.\d+)?)\s*,\s*([+-]?\d+(?:\.\d+)?)',  # Dezimalformat
        ]
        
        for pattern in lat_long_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 2:
                        # Dezimalformat: "lat, lon"
                        lat = float(match.group(1))
                        lon = float(match.group(2))
                    else:
                        # Grad/Minuten/Sekunden Format
                        lat_deg = int(match.group(1))
                        lat_min = int(match.group(2))
                        lat_sec = float(match.group(3))
                        lat_dir = match.group(4)
                        
                        lon_deg = int(match.group(5))
                        lon_min = int(match.group(6))
                        lon_sec = float(match.group(7))
                        lon_dir = match.group(8)
                        
                        # Konvertiere zu Dezimal
                        lat = lat_deg + lat_min/60 + lat_sec/3600
                        if lat_dir.upper() == 'S':
                            lat = -lat
                        
                        lon = lon_deg + lon_min/60 + lon_sec/3600
                        if lon_dir.upper() == 'W':
                            lon = -lon
                    
                    result.value = f"{lat:.6f}, {lon:.6f}"
                    result.unit = "Lat/Long"
                    result.confidence = 0.9
                    result.original_text = f"Lat/Long: {lat:.6f}, {lon:.6f}"
                    return result
                
                except (ValueError, TypeError):
                    continue
        
        # Wenn keine Koordinaten gefunden wurden
        result.error_message = "Keine gültigen Koordinaten gefunden"
        return result
    
    def normalize_mine_data(self, mine_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalisiert alle relevanten Felder in Mine-Daten
        
        Args:
            mine_data: Rohdaten der Mine
            
        Returns:
            Normalisierte Mine-Daten
        """
        normalized_data = mine_data.copy()
        
        # Normalisiere Fördermenge/Durchsatz
        production_fields = ['Fördermenge', 'Durchsatz', 'Produktionsrate', 'Kapazität']
        for field in production_fields:
            if field in normalized_data and normalized_data[field]:
                result = self.normalize_production_rate(str(normalized_data[field]))
                if result.is_valid():
                    normalized_data[field] = f"{result.value:.1f} {result.unit}"
                    self.logger.debug(f"Fördermenge normalisiert: {result.original_text}")
        
        # Normalisiere Flächenangaben (erweiterte Version)
        normalized_data = self._normalize_area_fields(normalized_data)
        
        # Normalisiere Koordinaten zu Lat/Long
        coord_fields = ['Koordinaten', 'Standort', 'Position', 'x-Koordinate', 'y-Koordinate']
        for field in coord_fields:
            if field in normalized_data and normalized_data[field]:
                result = self.normalize_coordinates(str(normalized_data[field]))
                
                if result.is_valid():
                    # Erstelle separate Lat/Lon-Felder für CSV
                    lat_lon_parts = result.value.split(', ')
                    if len(lat_lon_parts) >= 2:
                        normalized_data['Latitude_dd'] = lat_lon_parts[0]
                        normalized_data['Longitude_dd'] = lat_lon_parts[1]
                        
                        # Überschreibe die ursprünglichen Koordinatenfelder mit Lat/Lon
                        if field == 'x-Koordinate':
                            normalized_data['x-Koordinate'] = lat_lon_parts[0]  # Latitude
                        elif field == 'y-Koordinate':
                            normalized_data['y-Koordinate'] = lat_lon_parts[1]  # Longitude
                        else:
                            # Für andere Koordinatenfelder, verwende die kombinierte Koordinate
                            normalized_data[field] = result.value
                    
                    # Speichere auch die kombinierte Koordinate
                    normalized_data['LatLong_Koordinaten'] = result.value
                    
                    self.logger.debug(f"Koordinaten normalisiert: {result.original_text}")
                    
                    # Entferne ursprüngliches Feld nur wenn es nicht x-Koordinate oder y-Koordinate ist
                    if field not in ['x-Koordinate', 'y-Koordinate']:
                        del normalized_data[field]
        
        return normalized_data
    
    def _normalize_area_fields(self, mine_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalisiert Flächenfelder mit separaten Typen
        
        Args:
            mine_data: Mine-Daten
            
        Returns:
            Normalisierte Mine-Daten mit separaten Flächenfeldern
        """
        normalized_data = mine_data.copy()
        
        # Flächen-Typen und ihre Erkennungsmuster (angepasst an CSV-Vorlage)
        area_type_patterns = {
            'PAR': {
                'patterns': [r'PÀR', r'PAR', r'Plan d\'aménagement et de restauration', r'Restaurationsplan'],
                'target_unit': 'km²',
                'field_name': 'PAR Fläche der Mine in qkm'
            },
            'Claims': {
                'patterns': [r'Claims', r'Konzession', r'Concession', r'Lizenzgebiet'],
                'target_unit': 'km²', 
                'field_name': 'Claims Fläche der Mine in qkm'
            },
            'Gesamtfläche': {
                'patterns': [r'Gesamtfläche', r'Total area', r'genutzte Bereiche', r'utilisée'],
                'target_unit': 'km²',
                'field_name': 'Gesamtfläche der Mine in qkm'
            },
            'Minenfläche': {
                'patterns': [r'Fläche der Mine', r'Mine area', r'Betriebsfläche'],
                'target_unit': 'km²',
                'field_name': 'Fläche der Mine in qkm'
            }
        }
        
        # Durchsuche alle Felder nach Flächenangaben
        for field_name, field_value in mine_data.items():
            if not field_value or not isinstance(field_value, str):
                continue
            
            field_text = str(field_value).lower()
            
            # Bestimme Flächentyp basierend auf Feldname und Inhalt
            detected_type = None
            
            # Prüfe zuerst, ob es sich um ein Standard-CSV-Feld handelt
            csv_field_mapping = {
                'PAR Fläche der Mine in qkm': 'PAR',
                'Claims Fläche der Mine in qkm': 'Claims', 
                'Gesamtfläche der Mine in qkm': 'Gesamtfläche',
                'Fläche der Mine in qkm': 'Minenfläche'
            }
            
            if field_name in csv_field_mapping:
                detected_type = csv_field_mapping[field_name]
            else:
                # Fallback: Pattern-basierte Erkennung
                for area_type, config in area_type_patterns.items():
                    # Prüfe Feldname
                    if any(pattern.lower() in field_name.lower() for pattern in config['patterns']):
                        detected_type = area_type
                        break
                    
                    # Prüfe Feldinhalt
                    if any(pattern.lower() in field_text for pattern in config['patterns']):
                        detected_type = area_type
                        break
                
                # Wenn kein spezifischer Typ erkannt wurde, verwende Standard
                if not detected_type:
                    if 'fläche' in field_name.lower() or 'area' in field_name.lower():
                        detected_type = 'Minenfläche'
            
            if detected_type:
                config = area_type_patterns[detected_type]
                result = self.normalize_area(field_value, config['target_unit'])
                
                if result.is_valid():
                    # Verwende das Standard-CSV-Feld oder erstelle ein neues
                    if field_name in csv_field_mapping:
                        # Direkte Normalisierung des bestehenden Feldes
                        # Wichtig: Nur den normalisierten Wert speichern, nicht mehrere Werte
                        normalized_data[field_name] = f"{result.value:.4f} {config['target_unit']}"
                        self.logger.debug(f"CSV-Feld normalisiert: {field_name}: {result.original_text}")
                    else:
                        # Erstelle neues Feld mit spezifischem Namen
                        new_field_name = config['field_name']
                        normalized_data[new_field_name] = f"{result.value:.4f} {config['target_unit']}"
                        
                        # Markiere ursprüngliches Feld als verarbeitet
                        normalized_data[f"{field_name}_ORIGINAL"] = field_value
                        
                        self.logger.debug(f"Fläche normalisiert: {field_name} → {new_field_name}: {result.original_text}")
        
        return normalized_data