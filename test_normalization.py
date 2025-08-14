#!/usr/bin/env python3
"""
Test-Skript für die neue Einheiten-Normalisierung
"""

import sys
import os

# Füge Projekt-Root zum Python-Path hinzu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mine_extractor_refactored.utils.unit_converter import UnitConverter
from mine_extractor_refactored.utils.logger import MineExtractorLogger


def test_production_rate_normalization():
    """Testet Fördermengen-Normalisierung"""
    print("🔧 Test: Fördermengen-Normalisierung")
    print("=" * 50)
    
    converter = UnitConverter()
    
    test_cases = [
        "2,4 Mt/Jahr; >400 000 oz Au; 6 600 t/j",
        "2.4 Mt/Jahr",
        ">400 000 oz Au",
        "6 600 t/j",
        "1.5 million tonnes/year",
        "~500 oz/jahr",
    ]
    
    for test_case in test_cases:
        result = converter.normalize_production_rate(test_case)
        print(f"Input:  {test_case}")
        if result.is_valid():
            print(f"Output: {result.value:.1f} {result.unit}")
            print(f"Info:   {result.original_text}")
        else:
            print(f"Error:  {result.error_message}")
        print(f"Confidence: {result.confidence:.2f}")
        print()


def test_area_normalization():
    """Testet Flächen-Normalisierung"""
    print("🔧 Test: Flächen-Normalisierung")
    print("=" * 50)
    
    converter = UnitConverter()
    
    test_cases = [
        ("70,9 ha", "ha"),
        ("77,8 ha", "ha"),
        ("189,8496 km²", "ha"),
        ("2,848 km²", "ha"),
        ("284,8 ha", "km²"),
        ("18 984,96 ha", "km²"),
    ]
    
    for test_case, target_unit in test_cases:
        result = converter.normalize_area(test_case, target_unit)
        print(f"Input:  {test_case} → {target_unit}")
        if result.is_valid():
            print(f"Output: {result.value:.4f} {result.unit}")
            print(f"Info:   {result.original_text}")
        else:
            print(f"Error:  {result.error_message}")
        print(f"Confidence: {result.confidence:.2f}")
        print()


def test_coordinate_normalization():
    """Testet Koordinaten-Normalisierung"""
    print("🔧 Test: Koordinaten-Normalisierung")
    print("=" * 50)
    
    converter = UnitConverter()
    
    test_cases = [
        "426542; -77.42",
        "UTM E=426 542 / N=5 839 397",
        "52°41'58.37\" N / 76°05'13.13\" O",
        "426542; 5839397",
    ]
    
    for test_case in test_cases:
        result = converter.normalize_coordinates(test_case)
        print(f"Input:  {test_case}")
        
        if result.is_valid():
            print(f"Output: {result.value}")
            print(f"Info:   {result.original_text}")
            print(f"Confidence: {result.confidence:.1f}")
        else:
            print(f"Error:  {result.error_message}")
            print(f"Confidence: {result.confidence:.1f}")
        print()


def test_mine_data_normalization():
    """Testet komplette Mine-Daten-Normalisierung"""
    print("🔧 Test: Komplette Mine-Daten-Normalisierung")
    print("=" * 50)
    
    converter = UnitConverter()
    
    # Test-Daten mit neuen CSV-Feldern
    test_mine_data = {
        "Name der Mine": "Fénélon",
        "Fördermenge": "2,4 Mt/Jahr; >400 000 oz Au; 6 600 t/j",
        "Fläche der Mine in qkm": "77,8 ha",
        "PAR Fläche der Mine in qkm": "70,9 ha",
        "Claims Fläche der Mine in qkm": "189,8496 km²",
        "Gesamtfläche der Mine in qkm": "2,848 km²",
        "Koordinaten": "426542; -77.42",
        "Standort": "UTM E=426 542 / N=5 839 397",
    }
    
    print("Vor der Normalisierung:")
    for key, value in test_mine_data.items():
        print(f"  {key}: {value}")
    
    print("\nNach der Normalisierung:")
    normalized_data = converter.normalize_mine_data(test_mine_data)
    
    for key, value in normalized_data.items():
        print(f"  {key}: {value}")
    
    print("\nNeue spezifische Flächenfelder:")
    area_fields = [k for k in normalized_data.keys() if 'Fläche' in k or 'area' in k.lower()]
    for field in sorted(area_fields):
        if field in normalized_data:
            print(f"  {field}: {normalized_data[field]}")


def test_csv_field_normalization():
    """Testet spezifisch die neuen CSV-Felder"""
    print("🔧 Test: CSV-Feld-Normalisierung")
    print("=" * 50)
    
    converter = UnitConverter()
    
    # Test nur die neuen CSV-Felder
    csv_test_data = {
        "PAR Fläche der Mine in qkm": "77,8 ha",
        "Claims Fläche der Mine in qkm": "18984,96 ha", 
        "Gesamtfläche der Mine in qkm": "284,8 ha",
        "Fläche der Mine in qkm": "0,778 km²"
    }
    
    print("CSV-Felder vor Normalisierung:")
    for key, value in csv_test_data.items():
        print(f"  {key}: {value}")
    
    print("\nCSV-Felder nach Normalisierung:")
    normalized_data = converter.normalize_mine_data(csv_test_data)
    
    for key, value in normalized_data.items():
        if 'Fläche' in key:
            print(f"  {key}: {value}")
    
    print("\nErwartete Ergebnisse:")
    print("  PAR Fläche der Mine in qkm: 0.7780 km²")
    print("  Claims Fläche der Mine in qkm: 189.8496 km²") 
    print("  Gesamtfläche der Mine in qkm: 2.8480 km²")
    print("  Fläche der Mine in qkm: 0.7780 km²")


def main():
    """Hauptfunktion"""
    print("🧪 MineExtractor v6 - Einheiten-Normalisierung Test")
    print("=" * 60)
    print()
    
    try:
        test_production_rate_normalization()
        test_area_normalization()
        test_coordinate_normalization()
        test_mine_data_normalization()
        test_csv_field_normalization()
        
        print("✅ Alle Tests abgeschlossen!")
        
    except Exception as e:
        print(f"❌ Fehler beim Testen: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()