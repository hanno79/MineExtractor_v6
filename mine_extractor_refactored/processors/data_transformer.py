"""
Datentransformation und Chunk-Verarbeitung für den Mine Extractor
"""

import time
import asyncio
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

from ..config.settings import (
    PROCESSING_LARGE_FILE_CHUNK_SIZE, PROCESSING_MAX_CHUNK_SIZE, MIN_CHUNK_WORKERS,
    MAX_CHUNK_WORKERS, DEFAULT_CELL_SEPARATOR, MAX_CHUNKS_PER_FILE
)
from ..models.data_models import (
    MineData, ChunkResult, ProcessingResult, FileInfo, APIResponse
)
from ..utils.exceptions import ChunkProcessingError, DataTypeError
from ..utils.logger import MineExtractorLogger
from ..utils.helpers import HardwareUtils
from .agents import AgentManager
from .table_parser import TableParser


@dataclass
class ChunkInfo:
    """Information über einen zu verarbeitenden Chunk"""
    chunk_id: str
    chunk_text: str
    file_basename: str
    chunk_description: str
    chunk_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.chunk_size = len(self.chunk_text)


@dataclass
class TransformationResult:
    """Ergebnis einer Datentransformation"""
    success: bool
    transformed_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    warnings: List[str] = None
    processing_time: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []
        if self.metadata is None:
            self.metadata = {}


class ChunkProcessor:
    """Verarbeitet große Dateien in Chunks"""

    def __init__(self, api_client_manager, logger: Optional[MineExtractorLogger] = None):
        self.api_client_manager = api_client_manager
        self.logger = logger or MineExtractorLogger("ChunkProcessor")
        self.abort_processing = False

        # Hardware-Info für Optimierung
        self.system_info = HardwareUtils.get_system_info()
        
        # Tabellen-Parser für strukturierte Daten
        self.table_parser = TableParser(logger)

    def _get_max_chunks_per_file(self) -> int:
        """
        Ermittelt die maximale Anzahl von Chunks pro Datei aus der Konfiguration.
        
        Returns:
            Maximale Anzahl von Chunks pro Datei (Standard: 24)
        """
        try:
            # Versuche, die Einstellung aus der Konfiguration zu laden
            from ..config.settings import get_config
            config = get_config()
            max_chunks = config.get("max_chunks_per_file", MAX_CHUNKS_PER_FILE)
            
            # Validierung: Stelle sicher, dass es eine positive Ganzzahl ist
            if not isinstance(max_chunks, int) or max_chunks <= 0:
                self.logger.warning(f"Ungültige max_chunks_per_file Konfiguration: {max_chunks}. Verwende Standard: {MAX_CHUNKS_PER_FILE}")
                return MAX_CHUNKS_PER_FILE
            
            return max_chunks
        except Exception as e:
            # Fallback auf Standard-Wert bei Fehlern
            self.logger.warning(f"Fehler beim Laden der max_chunks_per_file Konfiguration: {e}. Verwende Standard: {MAX_CHUNKS_PER_FILE}")
            return MAX_CHUNKS_PER_FILE

    def create_chunks(self, content: str, file_basename: str,
                     chunk_size: int = PROCESSING_LARGE_FILE_CHUNK_SIZE,
                     overlap_size: int = 500) -> List[ChunkInfo]:
        """
        Erstellt Chunks aus großem Inhalt mit Kontext-Überlappung

        Args:
            content: Zu teilender Inhalt
            file_basename: Dateiname für Referenz
            chunk_size: Maximale Chunk-Größe
            overlap_size: Überlappung zwischen Chunks für Kontext

        Returns:
            Liste von ChunkInfo-Objekten
        """
        content_length = len(content)

        # Falls Inhalt bereits klein genug ist, nur einen Chunk erzeugen
        if content_length <= chunk_size:
            return [ChunkInfo(
                chunk_id="SINGLE",
                chunk_text=f"'{file_basename}' (VOLLSTÄNDIG)\n\n{content}",
                file_basename=file_basename,
                chunk_description="Vollständiger Inhalt",
                chunk_size=content_length,
                metadata={"has_overlap": False}
            )]

        # Token-sichere Chunkbildung: harte Obergrenze pro Chunk einhalten
        chunks: List[ChunkInfo] = []
        start_idx = 0
        chunk_index = 1

        # Maximalzahl an Chunks begrenzen, um Laufzeit/Calls zu kontrollieren
        max_chunks = self._get_max_chunks_per_file()

        while start_idx < content_length and chunk_index <= max_chunks:
            # Kontext-Überlappung für bessere Ergebnisse
            effective_start = max(0, start_idx - overlap_size) if chunk_index > 1 else start_idx
            end_idx = min(start_idx + chunk_size, content_length)
            
            # Chunk mit Kontext extrahieren
            if chunk_index > 1 and effective_start < start_idx:
                chunk_content = content[effective_start:end_idx]
                context_marker = f"[...Kontext-Überlappung: {start_idx - effective_start} Zeichen...]\n"
            else:
                chunk_content = content[start_idx:end_idx]
                context_marker = ""

            # Beschreibung basierend auf Position
            if start_idx == 0:
                description = "Anfangsbereich"
            elif end_idx >= content_length:
                description = "Endbereich"
            else:
                description = f"Bereich {chunk_index}"

            chunks.append(ChunkInfo(
                chunk_id=f"CHUNK-{chunk_index}",
                chunk_text=f"'{file_basename}' ({description.upper()})\n{context_marker}\n{chunk_content}",
                file_basename=file_basename,
                chunk_description=description,
                chunk_size=len(chunk_content),
                metadata={
                    "has_overlap": chunk_index > 1,
                    "overlap_start": effective_start,
                    "chunk_start": start_idx,
                    "chunk_end": end_idx
                }
            ))

            # Nächster Start mit leichter Überlappung
            start_idx = end_idx - (overlap_size // 4) if end_idx < content_length else end_idx
            chunk_index += 1

        # Falls der Inhalt noch nicht vollständig abgedeckt ist (wegen max_chunks), den Rest an den letzten Chunk anhängen
        if start_idx < content_length and chunks:
            remainder = content[start_idx:]
            last = chunks[-1]
            combined_text = f"{last.chunk_text}{remainder}"
            chunks[-1] = ChunkInfo(
                chunk_id=last.chunk_id,
                chunk_text=combined_text,
                file_basename=last.file_basename,
                chunk_description=last.chunk_description,
                chunk_size=len(combined_text)
            )

        self.logger.process(f"Erstellt {len(chunks)} Chunks für {file_basename} ({content_length:,} Zeichen; max {chunk_size} pro Chunk)")
        return chunks

    def process_chunks_async(self, chunks: List[ChunkInfo],
                           max_workers: Optional[int] = None) -> List[ChunkResult]:
        """
        Verarbeitet Chunks sequentiell für bessere Stabilität

        Args:
            chunks: Liste von ChunkInfo-Objekten
            max_workers: Wird ignoriert (sequentiell)

        Returns:
            Liste von ChunkResult-Objekten
        """
        if not chunks:
            return []

        # Sequentielle Verarbeitung

        results = []

        # Sequentielle Verarbeitung für bessere Stabilität
        for i, chunk in enumerate(chunks, 1):
            if self.abort_processing:
                self.logger.warning("🛑 Chunk-Verarbeitung abgebrochen")
                break

            try:
                # Log wird bereits in _process_single_chunk ausgegeben
                result = self._process_single_chunk(chunk)
                results.append(result)
                self.logger.success(f"Chunk {chunk.chunk_id} erfolgreich verarbeitet")

                # Kurze Pause zwischen Chunks
                if i < len(chunks):
                    time.sleep(0.5)

            except Exception as e:
                self.logger.error(f"💥 Fehler bei Chunk {chunk.chunk_id}: {e}")
                # Erstelle Fehler-Result
                results.append(ChunkResult(
                    chunk_id=chunk.chunk_id,
                    chunk_description=chunk.chunk_description,
                    success=False,
                    error_message=str(e),
                    extracted_data={},
                    confidence_score=0.0
                ))

        # Chunk-Verarbeitung abgeschlossen
        return results

    def _process_single_chunk(self, chunk: ChunkInfo) -> ChunkResult:
        """
        Verarbeitet einen einzelnen Chunk
        
        Args:
            chunk: Zu verarbeitender Chunk
            
        Returns:
            ChunkResult
        """
        start_time = time.time()
        
        try:
            self.logger.info(f"Verarbeite Chunk {chunk.chunk_id}: {chunk.chunk_description}")
            
            if self.abort_processing:
                return ChunkResult(
                    chunk_id=chunk.chunk_id,
                    chunk_description=chunk.chunk_description,
                    success=False,
                    error_message="Verarbeitung abgebrochen"
                )
            
            # Sprache grob schätzen und als Hint voranstellen (LLM darf beides verstehen, Prompt bleibt DE-Keys)
            from ..processors.data_parser import ContentAnalyzer
            analyzer = ContentAnalyzer(self.logger)
            analysis = analyzer.analyze_content(chunk.chunk_text)
            lang_hint = analysis.get("estimated_language", "unknown")
            
            # Suche nach Tabellen im Chunk
            tables = self.table_parser.extract_tables(chunk.chunk_text)
            table_hint = ""
            if tables:
                self.logger.debug(f"Chunk {chunk.chunk_id}: {len(tables)} Tabellen gefunden")
                # Füge Tabellen-Hinweis hinzu
                table_hint = f"\n[TABLES_FOUND={len(tables)}]\n"
                for i, table in enumerate(tables):
                    table_dict = table.to_dict()
                    if table_dict:
                        table_hint += f"[TABLE_{i+1}_TYPE={table.table_type}]\n"
            
            hint_prefix = f"[language_hint={lang_hint}]{table_hint}\n"
            chunk_payload = hint_prefix + chunk.chunk_text

            # API-Aufruf für Chunk
            api_result = self.api_client_manager.call_api_with_fallback(
                content=chunk_payload,
                max_tokens=2000,
                timeout=180,
                max_retries=2
            )
            
            processing_time = time.time() - start_time
            
            if not api_result.success:
                return ChunkResult(
                    chunk_id=chunk.chunk_id,
                    chunk_description=chunk.chunk_description,
                    success=False,
                    error_message=api_result.error_message,
                    processing_time=processing_time
                )
            
            # Extrahiere Daten aus API-Response
            from ..utils.helpers import JSONUtils
            import json
            
            json_str = JSONUtils.extract_json_from_text(api_result.content)
            if json_str:
                try:
                    data_dict = json.loads(json_str)
                    return ChunkResult(
                        chunk_id=chunk.chunk_id,
                        chunk_description=chunk.chunk_description,
                        success=True,
                        extracted_data=data_dict,
                        processing_time=processing_time
                    )
                except json.JSONDecodeError:
                    pass

            # Wenn die erste Runde kein JSON liefert und OpenRouter verfügbar ist, versuche explizit die Modellkaskade
            try:
                use_or = getattr(self.api_client_manager.config, 'use_openrouter_for_all', False)
                models = getattr(self.api_client_manager, 'model_order', None)
                if use_or and models and self.api_client_manager.has_openrouter():
                    def _json_validator(text: str) -> bool:
                        from ..utils.helpers import JSONUtils
                        return bool(JSONUtils.extract_json_from_text(text or ""))
                    or_result = self.api_client_manager.call_with_model_fallback(
                        chunk_payload,
                        models,
                        max_tokens=1200,
                        timeout=120,
                        max_retries=2,
                        use_json_prompt=True,
                        content_validator=_json_validator
                    )
                    if or_result and or_result.success and or_result.content:
                        json_str2 = JSONUtils.extract_json_from_text(or_result.content)
                        if json_str2:
                            try:
                                data_dict2 = json.loads(json_str2)
                                return ChunkResult(
                                    chunk_id=chunk.chunk_id,
                                    chunk_description=chunk.chunk_description,
                                    success=True,
                                    extracted_data=data_dict2,
                                    processing_time=processing_time
                                )
                            except json.JSONDecodeError:
                                pass
            except Exception:
                pass
            
            return ChunkResult(
                chunk_id=chunk.chunk_id,
                chunk_description=chunk.chunk_description,
                success=False,
                error_message="Kein gültiges JSON in API-Response gefunden",
                processing_time=processing_time
            )
                
        except Exception as e:
            processing_time = time.time() - start_time
            return ChunkResult(
                chunk_id=chunk.chunk_id,
                chunk_description=chunk.chunk_description,
                success=False,
                error_message=f"Chunk-Verarbeitung fehlgeschlagen: {e}",
                processing_time=processing_time
            )

    def combine_chunk_results(self, chunk_results: List[ChunkResult],
                            cell_separator: str = DEFAULT_CELL_SEPARATOR) -> TransformationResult:
        """
        Kombiniert Ergebnisse aus mehreren Chunks

        Args:
            chunk_results: Liste von ChunkResult-Objekten
            cell_separator: Trennzeichen für Zelleninhalte

        Returns:
            TransformationResult mit kombinierten Daten
        """
        start_time = time.time()

        successful_results = [r for r in chunk_results if r.success and r.extracted_data]

        if not successful_results:
            return TransformationResult(
                success=False,
                error_message="Keine erfolgreichen Chunk-Ergebnisse zum Kombinieren",
                processing_time=time.time() - start_time
            )

        # Kombiniere alle Daten
        combined_data = {}
        warnings = []

        for result in successful_results:
            chunk_data = result.extracted_data

            for key, value in chunk_data.items():
                # Sichere String-Operationen
                from ..utils.helpers import SafeStringOperations
                safe_key = SafeStringOperations.safe_string_operation(key, "strip")
                safe_value = SafeStringOperations.safe_string_operation(value, "strip")

                if not safe_value:
                    continue

                if safe_key not in combined_data or not combined_data[safe_key]:
                    combined_data[safe_key] = safe_value
                elif safe_value and safe_key in combined_data:
                    # Kombiniere mit Separator, aber vermeide Duplikate
                    from ..utils.helpers import DataUtils
                    current_value = combined_data[safe_key]
                    combined_value = DataUtils.combine_values_with_separator(
                        current_value, safe_value, cell_separator
                    )
                    combined_data[safe_key] = combined_value

        processing_time = time.time() - start_time

        self.logger.success(f"Chunk-Ergebnisse kombiniert: {len(combined_data)} Felder aus {len(successful_results)} Chunks")

        return TransformationResult(
            success=True,
            transformed_data=combined_data,
            warnings=warnings,
            processing_time=processing_time,
            metadata={
                "total_chunks": len(chunk_results),
                "successful_chunks": len(successful_results),
                "combined_fields": len(combined_data)
            }
        )

    def abort(self):
        """Bricht Chunk-Verarbeitung ab"""
        self.abort_processing = True
        self.logger.warning("Chunk-Verarbeitung wird abgebrochen...")


class DataTransformer:
    """Transformiert und normalisiert Daten"""

    def __init__(self, logger: Optional[MineExtractorLogger] = None):
        self.logger = logger or MineExtractorLogger("DataTransformer")

    def transform_api_response_to_mine_data(self, api_response_text: str,
                                          file_info: FileInfo) -> TransformationResult:
        """
        Transformiert API-Response zu MineData

        Args:
            api_response_text: API-Response Text
            file_info: Datei-Informationen

        Returns:
            TransformationResult
        """
        start_time = time.time()

        try:
            # Extrahiere JSON aus API-Response
            from ..utils.helpers import JSONUtils
            import json

            self.logger.debug(f"API Response Text: {api_response_text[:500]}...")
            json_str = JSONUtils.extract_json_from_text(api_response_text)
            if not json_str:
                self.logger.error("Kein JSON in API-Response gefunden")
                return TransformationResult(
                    success=False,
                    error_message="Kein JSON in API-Response gefunden",
                    processing_time=time.time() - start_time
                )
            self.logger.debug(f"Extrahierter JSON String: {json_str[:500]}...")

            try:
                mine_dict = json.loads(json_str)
                self.logger.debug(f"Geparstes Mine Dictionary: {mine_dict}")
            except json.JSONDecodeError as e:
                # Versuche JSON-Reparatur
                repaired_json = JSONUtils.repair_json(json_str)
                if repaired_json:
                    try:
                        mine_dict = json.loads(repaired_json)
                    except json.JSONDecodeError:
                        return TransformationResult(
                            success=False,
                            error_message=f"JSON-Parsing und -Reparatur fehlgeschlagen: {e}",
                            processing_time=time.time() - start_time
                        )
                else:
                    return TransformationResult(
                        success=False,
                        error_message=f"JSON-Parsing und -Reparatur fehlgeschlagen: {e}",
                        processing_time=time.time() - start_time
                    )


            # Stelle sicher, dass 'Name der Mine' immer vorhanden ist
            if "Name der Mine" not in mine_dict:
                mine_dict["Name der Mine"] = ""

            if file_info.extracted_mine_id:
                mine_dict["Datei_ID"] = file_info.extracted_mine_id

            if file_info.extracted_date:
                if "Jahr der Erstellung des Dokuments" not in mine_dict or not mine_dict["Jahr der Erstellung des Dokuments"]:
                    year_match = file_info.extracted_date.split('-')[0]
                    if year_match.isdigit():
                        mine_dict["Jahr der Erstellung des Dokuments"] = year_match

            processing_time = time.time() - start_time

            return TransformationResult(
                success=True,
                transformed_data=mine_dict,
                processing_time=processing_time,
                metadata={
                    "file_basename": file_info.file_basename,
                    "file_size": file_info.file_size
                }
            )

        except Exception as e:
            return TransformationResult(
                success=False,
                error_message=f"Transformation fehlgeschlagen: {e}",
                processing_time=time.time() - start_time
            )

    def enhance_mine_data_with_matching(self, mine_data: Dict[str, Any],
                                      file_info: FileInfo,
                                      known_mine_names: List[str]) -> TransformationResult:
        """
        Verbessert Mine-Daten mit Name-Matching

        Args:
            mine_data: Mine-Daten Dictionary
            file_info: Datei-Informationen
            known_mine_names: Bekannte Minennamen

        Returns:
            TransformationResult mit verbesserter Zuordnung
        """
        start_time = time.time()
        enhanced_data = mine_data.copy()
        warnings = []

        try:
            extracted_mine_name = enhanced_data.get("Name der Mine", "")

            # Versuche Mine-Matching
            if extracted_mine_name:
                from ..utils.helpers import MineNameProcessor
                best_match = MineNameProcessor.find_best_mine_match(
                    extracted_mine_name,
                    file_info.potential_mine_names,
                    known_mine_names
                )

                if best_match and best_match != extracted_mine_name:
                    self.logger.match(f"Mine-Matching: '{extracted_mine_name}' -> '{best_match}'")
                    enhanced_data["Name der Mine"] = best_match
                    enhanced_data["Original_Extrahierter_Name"] = extracted_mine_name
                elif not best_match:
                    warnings.append(f"Keine Zuordnung für extrahierten Namen: '{extracted_mine_name}'")

                    # Ähnliche Namen für Diagnose
                    similar_names = MineNameProcessor.find_similar_mine_names(
                        extracted_mine_name, known_mine_names, limit=3
                    )
                    if similar_names:
                        warnings.append(f"Ähnliche bekannte Namen: {similar_names}")

            # Fallback: Versuche Namen aus Dateiname
            elif file_info.potential_mine_names:
                for potential_name in file_info.potential_mine_names:
                    match = MineNameProcessor.find_best_mine_match(
                        potential_name, [], known_mine_names
                    )
                    if match:
                        self.logger.match(f"Mine über Dateiname zugeordnet: '{potential_name}' -> '{match}'")
                        enhanced_data["Name der Mine"] = match
                        enhanced_data["Quelle_Name_Matching"] = "Dateiname"
                        break
                else:
                    warnings.append("Keine Mine-Zuordnung möglich (weder extrahiert noch Dateiname)")

            processing_time = time.time() - start_time

            return TransformationResult(
                success=True,
                transformed_data=enhanced_data,
                warnings=warnings,
                processing_time=processing_time,
                metadata={
                    "matching_performed": True,
                    "original_name": extracted_mine_name,
                    "final_name": enhanced_data.get("Name der Mine", ""),
                    "potential_filename_names": file_info.potential_mine_names
                }
            )

        except Exception as e:
            return TransformationResult(
                success=False,
                error_message=f"Mine-Matching fehlgeschlagen: {e}",
                warnings=warnings,
                processing_time=time.time() - start_time
            )

    def normalize_field_values(self, data: Dict[str, Any]) -> TransformationResult:
        """
        Normalisiert Feldwerte (Trim, Format, etc.)

        Args:
            data: Zu normalisierende Daten

        Returns:
            TransformationResult mit normalisierten Daten
        """
        start_time = time.time()
        normalized_data = {}
        warnings = []

        try:
            for key, value in data.items():
                if not value:
                    normalized_data[key] = ""
                    continue

                # Sichere String-Operationen
                from ..utils.helpers import SafeStringOperations
                normalized_key = SafeStringOperations.safe_string_operation(key, "strip")
                normalized_value = SafeStringOperations.safe_string_operation(value, "strip")

                # Spezielle Normalisierungen
                if "Name der Mine" in normalized_key and normalized_value:
                    # Normalisiere Mine-Namen
                    from ..utils.helpers import MineNameProcessor
                    normalized_mine_name = MineNameProcessor.normalize_mine_name(normalized_value)
                    if normalized_mine_name != normalized_value.lower():
                        # Behalte Original-Kapitalisierung wenn möglich
                        normalized_data[normalized_key] = normalized_value
                    else:
                        normalized_data[normalized_key] = normalized_value

                elif "Jahr" in normalized_key and normalized_value:
                    # Extrahiere Jahr aus Text
                    year_match = re.search(r'\b(19|20)\d{2}\b', normalized_value)
                    if year_match:
                        normalized_data[normalized_key] = year_match.group()
                    else:
                        normalized_data[normalized_key] = normalized_value
                        warnings.append(f"Kein gültiges Jahr in '{normalized_key}': '{normalized_value}'")

                elif "Kosten" in normalized_key and normalized_value:
                    # Normalisiere Kosten-Format
                    # Entferne überflüssige Leerzeichen, aber behalte Struktur
                    cleaned_costs = re.sub(r'\s+', ' ', normalized_value)
                    normalized_data[normalized_key] = cleaned_costs

                else:
                    # Standard-Normalisierung
                    normalized_data[normalized_key] = normalized_value

            processing_time = time.time() - start_time

            return TransformationResult(
                success=True,
                transformed_data=normalized_data,
                warnings=warnings,
                processing_time=processing_time,
                metadata={
                    "normalized_fields": len(normalized_data),
                    "empty_fields": sum(1 for v in normalized_data.values() if not v)
                }
            )

        except Exception as e:
            return TransformationResult(
                success=False,
                error_message=f"Normalisierung fehlgeschlagen: {e}",
                processing_time=time.time() - start_time
            )


class ProcessingOrchestrator:
    """Orchestriert den gesamten Verarbeitungsprozess"""

    def __init__(self, api_client_manager, known_mine_names: List[str] = None,
                 logger: Optional[MineExtractorLogger] = None,
                 header_fields: Optional[List[str]] = None):
        self.api_client_manager = api_client_manager
        self.known_mine_names = known_mine_names or []
        self.logger = logger or MineExtractorLogger("ProcessingOrchestrator")
        self.header_fields = header_fields or []

        self.chunk_processor = ChunkProcessor(api_client_manager, logger)
        self.data_transformer = DataTransformer(logger)
        self.agent_manager = None  # wird durch Core gesetzt
        
        # Thread-sicherer Lock für lazy initialization des agent_manager
        self._agent_manager_lock = threading.RLock()

    def process_content(self, content: str, file_info: FileInfo,
                       use_chunks: bool = None) -> ProcessingResult:
        """
        Verarbeitet Dateiinhalt komplett

        Args:
            content: Dateiinhalt
            file_info: Datei-Informationen
            use_chunks: Ob Chunk-Verarbeitung verwendet werden soll

        Returns:
            ProcessingResult
        """
        start_time = time.time()

        # Entscheide über Chunk-Verarbeitung
        if use_chunks is None:
            use_chunks = len(content) > PROCESSING_MAX_CHUNK_SIZE
        
        # Analysiere Dokumentsprache einmal global
        from ..processors.data_parser import ContentAnalyzer
        analyzer = ContentAnalyzer(self.logger)
        doc_analysis = analyzer.analyze_content(content[:10000])  # Erste 10k Zeichen
        doc_language = doc_analysis.get("estimated_language", "unknown")
        self.logger.info(f"Dokument-Sprache erkannt: {doc_language}")

        try:
            if use_chunks:
                return self._process_with_chunks(content, file_info, start_time)
            else:
                return self._process_without_chunks(content, file_info, start_time)

        except Exception as e:
            processing_time = time.time() - start_time
            return ProcessingResult(
                file_info=file_info,
                success=False,
                error_message=f"Verarbeitung fehlgeschlagen: {e}",
                processing_time=processing_time
            )

    def _process_without_chunks(self, content: str, file_info: FileInfo,
                              start_time: float) -> ProcessingResult:
        """Verarbeitet ohne Chunks"""
        # Direkte API-Verarbeitung
        from ..utils.helpers import JSONUtils
        import json

        api_result = self.api_client_manager.call_api_with_fallback(
            content=content,
            max_tokens=4000,
            timeout=180,
            max_retries=3
        )

        if not api_result.success:
            processing_time = time.time() - start_time
            return ProcessingResult(
                file_info=file_info,
                success=False,
                error_message=api_result.error_message,
                processing_time=processing_time
            )

        # Transformiere zu MineData
        transform_result = self.data_transformer.transform_api_response_to_mine_data(
            api_result.content, file_info
        )

        if not transform_result.success:
            processing_time = time.time() - start_time
            return ProcessingResult(
                file_info=file_info,
                success=False,
                error_message=transform_result.error_message,
                processing_time=processing_time
            )

        # Verbessere mit Mine-Matching
        enhanced_result = self.data_transformer.enhance_mine_data_with_matching(
            transform_result.transformed_data, file_info, self.known_mine_names
        )

        # Erstelle finale MineData
        final_data = enhanced_result.transformed_data if enhanced_result.success else transform_result.transformed_data
        self.logger.debug(f"Final data before MineData.from_dict (without chunks): {final_data}")
        from ..models.data_models import MineData
        mine_data = MineData.from_dict(final_data)
        self.logger.debug(f"MineData object created (without chunks). Mine name: {mine_data.name}")

        processing_time = time.time() - start_time

        return ProcessingResult(
            file_info=file_info,
            mine_data=mine_data,
            success=True,
            processing_time=processing_time,
            api_response=None  # Könnte hier API-Response hinzufügen
        )

    def _process_with_chunks(self, content: str, file_info: FileInfo,
                           start_time: float) -> ProcessingResult:
        """Verarbeitet mit Chunks"""
        # Erstelle Chunks
        chunks = self.chunk_processor.create_chunks(content, file_info.file_basename)

        # Verarbeite Chunks parallel
        chunk_results = self.chunk_processor.process_chunks_async(chunks)

        # Kombiniere Ergebnisse
        combination_result = self.chunk_processor.combine_chunk_results(chunk_results)

        if not combination_result.success:
            processing_time = time.time() - start_time
            return ProcessingResult(
                file_info=file_info,
                success=False,
                error_message=combination_result.error_message,
                processing_time=processing_time,
                chunk_results=chunk_results
            )

        # Verbessere mit Mine-Matching
        enhanced_result = self.data_transformer.enhance_mine_data_with_matching(
            combination_result.transformed_data, file_info, self.known_mine_names
        )

        # Optional: fehlende Felder durch Agenten auffüllen (Hybrid-Strategie)
        final_data = enhanced_result.transformed_data if enhanced_result.success else combination_result.transformed_data
        try:
            from ..models.data_models import ExtractionConfig
            # Wenn Hybrid/Agenten aktiviert: per Config steuern
            strategy = getattr(self.api_client_manager.config, 'extraction_strategy', 'hybrid')
            if strategy in ('agents_per_field', 'hybrid'):
                # Thread-sichere lazy initialization mit Double-Checked Locking
                if self.agent_manager is None:
                    with self._agent_manager_lock:
                        if self.agent_manager is None:
                            self.agent_manager = AgentManager(
                                self.api_client_manager,
                                self.api_client_manager.config,
                                self.logger,
                                header_fields=self.header_fields
                            )
                # Backfill-Phase: wir übergeben auch die Chunks, damit OR pro-Chunk versucht wird
                final_data = self.agent_manager.fill_missing_fields(content, final_data, chunks=chunks)
        except Exception as e:
            self.logger.warning(f"Agenten-Auffüllen übersprungen: {e}")
        from ..models.data_models import MineData
        mine_data = MineData.from_dict(final_data)

        processing_time = time.time() - start_time

        return ProcessingResult(
            file_info=file_info,
            mine_data=mine_data,
            success=True,
            processing_time=processing_time,
            chunk_results=chunk_results
        )

    def update_known_mine_names(self, mine_names: List[str]):
        """Aktualisiert bekannte Minennamen"""
        self.known_mine_names = mine_names
        self.logger.info(f"Bekannte Minennamen aktualisiert: {len(mine_names)} Namen")

    def abort_processing(self):
        """Bricht Verarbeitung ab"""
        self.chunk_processor.abort()