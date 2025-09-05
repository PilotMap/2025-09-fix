"""
Centralized Aviation Weather API Client

This module provides a unified interface for all aviation weather API calls,
handling HTTP status codes, retry logic, XML parsing, and error handling.
"""

import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import time
import logging
# Simplified typing for Python 3.9.2 compatibility
import json
from datetime import datetime, timezone

# Configure logging
logger = logging.getLogger(__name__)

def parse_iso8601(s):
    """
    Parse ISO 8601 timestamp string to UTC datetime
    
    Args:
        s: ISO 8601 timestamp string (e.g., "2023-12-01T12:00:00Z")
        
    Returns:
        UTC datetime object or None if parsing fails
    """
    try:
        return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:
        return None

class AviationWeatherAPIError(Exception):
    """Base exception for aviation weather API errors"""
    pass

class NetworkError(AviationWeatherAPIError):
    """Network-related errors (timeout, connection refused, etc.)"""
    pass

class APIError(AviationWeatherAPIError):
    """API-related errors (4xx, 5xx status codes)"""
    pass

class FAAAPIClient:
    """Centralized client for Aviation Weather API calls"""
    
    def __init__(self, base_url="https://aviationweather.gov/api/data", 
                 timeout=30, max_retries=3, retry_delay=1.0):
        """
        Initialize the API client
        
        Args:
            base_url: Base URL for aviation weather API
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Initial delay between retries (exponential backoff)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
    def _make_request(self, endpoint: str, params: dict[str, str]) -> tuple[int, str]:
        """
        Make HTTP request with retry logic and error handling
        
        Args:
            endpoint: API endpoint (e.g., '/metar')
            params: Query parameters
            
        Returns:
            Tuple of (status_code, response_body)
            
        Raises:
            NetworkError: For network-related issues
            APIError: For API-related errors
        """
        url = f"{self.base_url}{endpoint}"
        
        # Add parameters to URL
        if params:
            query_string = urllib.parse.urlencode(params)
            url = f"{url}?{query_string}"
        
        logger.debug(f"Making request to: {url}")
        
        for attempt in range(self.max_retries + 1):
            try:
                request = urllib.request.Request(url)
                request.add_header('User-Agent', 'LiveSectional/1.0')
                
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    status_code = response.getcode()
                    response_body = response.read().decode('utf-8')
                    
                    logger.debug(f"Response status: {status_code}, body length: {len(response_body)}")
                    return status_code, response_body
                    
            except urllib.error.HTTPError as e:
                status_code = e.code
                response_body = e.read().decode('utf-8') if e.fp else ""
                
                if status_code == 204:
                    # 204 No Content is a valid response for empty data
                    logger.info("Received 204 No Content - no data available")
                    return status_code, ""
                elif 400 <= status_code < 500:
                    # Client error - don't retry
                    raise APIError(f"Client error {status_code}: {response_body}")
                elif 500 <= status_code < 600:
                    # Server error - retry
                    if attempt < self.max_retries:
                        delay = self.retry_delay * (2 ** attempt)
                        logger.warning(f"Server error {status_code}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries + 1})")
                        time.sleep(delay)
                        continue
                    else:
                        raise APIError(f"Server error {status_code} after {self.max_retries} retries: {response_body}")
                else:
                    raise APIError(f"Unexpected HTTP status {status_code}: {response_body}")
                    
            except (urllib.error.URLError, OSError) as e:
                if attempt < self.max_retries:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Network error: {e}, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries + 1})")
                    time.sleep(delay)
                    continue
                else:
                    raise NetworkError(f"Network error after {self.max_retries} retries: {e}")
                    
            except Exception as e:
                raise AviationWeatherAPIError(f"Unexpected error: {e}")
        
        # This should never be reached, but just in case
        raise AviationWeatherAPIError("Max retries exceeded")
    
    def _parse_xml(self, xml_content: str) -> ET.Element:
        """
        Parse XML content and return root element
        
        Args:
            xml_content: XML string to parse
            
        Returns:
            Root element of parsed XML
            
        Raises:
            APIError: If XML parsing fails
        """
        if not xml_content.strip():
            raise APIError("Empty XML response")
            
        try:
            return ET.fromstring(xml_content)
        except ET.ParseError as e:
            raise APIError(f"Failed to parse XML: {e}")
    
    def _chunk_airports(self, airports: list[str], chunk_size: int = 300) -> list[list[str]]:
        """
        Split airport list into chunks for large requests
        
        Args:
            airports: List of airport codes
            chunk_size: Maximum airports per chunk
            
        Returns:
            List of airport chunks
        """
        if not airports:
            return []
            
        chunks = []
        for i in range(0, len(airports), chunk_size):
            chunks.append(airports[i:i + chunk_size])
        return chunks
    
    def get_metars(self, airports: list[str], hours: int = 3, format: str = "xml") -> list[ET.Element]:
        """
        Get METAR data for specified airports
        
        Args:
            airports: List of airport codes (e.g., ['KJFK', 'KLAX'])
            hours: Number of hours of data to retrieve
            format: Response format ('xml' or 'json')
            
        Returns:
            List of METAR elements (empty list for 204 No Content)
            
        Raises:
            NetworkError: For network-related issues
            APIError: For API-related errors
        """
        if not airports:
            logger.warning("No airports provided for METAR request")
            return []
        
        # Validate airport codes (basic validation)
        valid_airports = [ap.strip().upper() for ap in airports if ap and ap.strip()]
        if not valid_airports:
            logger.warning("No valid airport codes provided")
            return []
        
        all_metars = []
        
        # Chunk airports if necessary
        airport_chunks = self._chunk_airports(valid_airports)
        
        for chunk in airport_chunks:
            params = {
                'format': format,
                'ids': ','.join(chunk),
                'hours': str(hours)
            }
            
            try:
                status_code, response_body = self._make_request('/metar', params)
                
                if status_code == 204:
                    # No data available for this chunk
                    logger.info(f"No METAR data available for airports: {chunk}")
                    continue
                
                if format == 'xml':
                    root = self._parse_xml(response_body)
                    # Find all METAR elements
                    metars = root.findall('.//METAR')
                    all_metars.extend(metars)
                    logger.info(f"Retrieved {len(metars)} METARs for airports: {chunk}")
                else:
                    # JSON format - convert to XML-like structure for compatibility
                    data = json.loads(response_body)
                    if 'data' in data:
                        for metar_data in data['data']:
                            # Create a simple element structure for compatibility
                            metar_elem = ET.Element('METAR')
                            for key, value in metar_data.items():
                                child = ET.SubElement(metar_elem, key)
                                child.text = str(value) if value is not None else ""
                            all_metars.append(metar_elem)
                    logger.info(f"Retrieved {len(data.get('data', []))} METARs for airports: {chunk}")
                    
            except (NetworkError, APIError) as e:
                logger.error(f"Chunk failed: {chunk}: {e}")
                raise
            except Exception as e:
                logger.exception(f"Unexpected error for chunk {chunk}")
                raise
        
        logger.info(f"Total METARs retrieved: {len(all_metars)}")
        return all_metars
    
    def get_tafs(self, airports: list[str], hours: int = 6, format: str = "xml") -> list[ET.Element]:
        """
        Get TAF data for specified airports
        
        Args:
            airports: List of airport codes
            hours: Number of hours of forecast data
            format: Response format ('xml' or 'json')
            
        Returns:
            List of TAF elements (empty list for 204 No Content)
            
        Raises:
            NetworkError: For network-related issues
            APIError: For API-related errors
        """
        if not airports:
            logger.warning("No airports provided for TAF request")
            return []
        
        # Validate airport codes
        valid_airports = [ap.strip().upper() for ap in airports if ap and ap.strip()]
        if not valid_airports:
            logger.warning("No valid airport codes provided")
            return []
        
        all_tafs = []
        
        # Chunk airports if necessary
        airport_chunks = self._chunk_airports(valid_airports)
        
        for chunk in airport_chunks:
            params = {
                'format': format,
                'ids': ','.join(chunk),
                'hours': str(hours)
            }
            
            try:
                status_code, response_body = self._make_request('/taf', params)
                
                if status_code == 204:
                    # No data available for this chunk
                    logger.info(f"No TAF data available for airports: {chunk}")
                    continue
                
                if format == 'xml':
                    root = self._parse_xml(response_body)
                    # Find all TAF elements
                    tafs = root.findall('.//TAF')
                    all_tafs.extend(tafs)
                    logger.info(f"Retrieved {len(tafs)} TAFs for airports: {chunk}")
                else:
                    # JSON format - convert to XML-like structure for compatibility
                    data = json.loads(response_body)
                    if 'data' in data:
                        for taf_data in data['data']:
                            # Create a simple element structure for compatibility
                            taf_elem = ET.Element('TAF')
                            for key, value in taf_data.items():
                                child = ET.SubElement(taf_elem, key)
                                child.text = str(value) if value is not None else ""
                            all_tafs.append(taf_elem)
                    logger.info(f"Retrieved {len(data.get('data', []))} TAFs for airports: {chunk}")
                    
            except (NetworkError, APIError) as e:
                logger.error(f"Chunk failed: {chunk}: {e}")
                raise
            except Exception as e:
                logger.exception(f"Unexpected error for chunk {chunk}")
                raise
        
        logger.info(f"Total TAFs retrieved: {len(all_tafs)}")
        return all_tafs
    
    def get_station_info(self, airports: list[str], format: str = "xml") -> list[ET.Element]:
        """
        Get station information for specified airports
        
        Args:
            airports: List of airport codes
            format: Response format ('xml' or 'json')
            
        Returns:
            List of station info elements (empty list for 204 No Content)
            
        Raises:
            NetworkError: For network-related issues
            APIError: For API-related errors
        """
        if not airports:
            logger.warning("No airports provided for station info request")
            return []
        
        # Validate airport codes
        valid_airports = [ap.strip().upper() for ap in airports if ap and ap.strip()]
        if not valid_airports:
            logger.warning("No valid airport codes provided")
            return []
        
        all_stations = []
        
        # Chunk airports if necessary
        airport_chunks = self._chunk_airports(valid_airports)
        
        for chunk in airport_chunks:
            params = {
                'format': format,
                'ids': ','.join(chunk)
            }
            
            try:
                status_code, response_body = self._make_request('/stationinfo', params)
                
                if status_code == 204:
                    # No data available for this chunk
                    logger.info(f"No station info available for airports: {chunk}")
                    continue
                
                if format == 'xml':
                    root = self._parse_xml(response_body)
                    # Find all station elements
                    stations = root.findall('.//Station')
                    all_stations.extend(stations)
                    logger.info(f"Retrieved {len(stations)} station info records for airports: {chunk}")
                else:
                    # JSON format - convert to XML-like structure for compatibility
                    data = json.loads(response_body)
                    if 'data' in data:
                        for station_data in data['data']:
                            # Create a simple element structure for compatibility
                            station_elem = ET.Element('Station')
                            for key, value in station_data.items():
                                child = ET.SubElement(station_elem, key)
                                child.text = str(value) if value is not None else ""
                            all_stations.append(station_elem)
                    logger.info(f"Retrieved {len(data.get('data', []))} station info records for airports: {chunk}")
                    
            except (NetworkError, APIError) as e:
                logger.error(f"Chunk failed: {chunk}: {e}")
                raise
            except Exception as e:
                logger.exception(f"Unexpected error for chunk {chunk}")
                raise
        
        logger.info(f"Total station info records retrieved: {len(all_stations)}")
        return all_stations
    
    def get_metars_cache(self, area: str = None, bbox: str = None, format: str = "xml") -> list[ET.Element]:
        """
        Get METAR data using cache endpoints for bulk retrieval
        
        Args:
            area: Geographic area (e.g., "US", "CA", "EU")
            bbox: Bounding box as "lat1,lon1,lat2,lon2"
            format: Response format ('xml' or 'json')
            
        Returns:
            List of METAR elements
            
        Note:
            This method uses cache endpoints which may have different data availability
            but can handle larger geographic areas more efficiently.
        """
        if not area and not bbox:
            raise ValueError("Either 'area' or 'bbox' must be specified")
        
        params = {'format': format}
        if area:
            params['area'] = area
        if bbox:
            params['bbox'] = bbox
        
        try:
            status_code, response_body = self._make_request('/metar/cache', params)
            
            if status_code == 204:
                logger.info("No METAR cache data available")
                return []
            
            if format == 'xml':
                root = self._parse_xml(response_body)
                metars = root.findall('.//METAR')
                logger.info(f"Retrieved {len(metars)} METARs from cache")
                return metars
            else:
                # JSON format - convert to XML-like structure for compatibility
                data = json.loads(response_body)
                metars = []
                if 'data' in data:
                    for metar_data in data['data']:
                        metar_elem = ET.Element('METAR')
                        for key, value in metar_data.items():
                            child = ET.SubElement(metar_elem, key)
                            child.text = str(value) if value is not None else ""
                        metars.append(metar_elem)
                logger.info(f"Retrieved {len(metars)} METARs from cache")
                return metars
                
        except (NetworkError, APIError) as e:
            logger.error(f"Cache request failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in cache request")
            raise
    
    def get_tafs_cache(self, area: str = None, bbox: str = None, format: str = "xml") -> list[ET.Element]:
        """
        Get TAF data using cache endpoints for bulk retrieval
        
        Args:
            area: Geographic area (e.g., "US", "CA", "EU")
            bbox: Bounding box as "lat1,lon1,lat2,lon2"
            format: Response format ('xml' or 'json')
            
        Returns:
            List of TAF elements
            
        Note:
            This method uses cache endpoints which may have different data availability
            but can handle larger geographic areas more efficiently.
        """
        if not area and not bbox:
            raise ValueError("Either 'area' or 'bbox' must be specified")
        
        params = {'format': format}
        if area:
            params['area'] = area
        if bbox:
            params['bbox'] = bbox
        
        try:
            status_code, response_body = self._make_request('/taf/cache', params)
            
            if status_code == 204:
                logger.info("No TAF cache data available")
                return []
            
            if format == 'xml':
                root = self._parse_xml(response_body)
                tafs = root.findall('.//TAF')
                logger.info(f"Retrieved {len(tafs)} TAFs from cache")
                return tafs
            else:
                # JSON format - convert to XML-like structure for compatibility
                data = json.loads(response_body)
                tafs = []
                if 'data' in data:
                    for taf_data in data['data']:
                        taf_elem = ET.Element('TAF')
                        for key, value in taf_data.items():
                            child = ET.SubElement(taf_elem, key)
                            child.text = str(value) if value is not None else ""
                        tafs.append(taf_elem)
                logger.info(f"Retrieved {len(tafs)} TAFs from cache")
                return tafs
                
        except (NetworkError, APIError) as e:
            logger.error(f"Cache request failed: {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in cache request")
            raise


# Convenience functions for backward compatibility
def get_metars(airports: list[str], hours: int = 3, format: str = "xml") -> list[ET.Element]:
    """Convenience function to get METARs using default client"""
    client = FAAAPIClient()
    return client.get_metars(airports, hours, format)

def get_tafs(airports: list[str], hours: int = 6, format: str = "xml") -> list[ET.Element]:
    """Convenience function to get TAFs using default client"""
    client = FAAAPIClient()
    return client.get_tafs(airports, hours, format)

def get_station_info(airports: list[str], format: str = "xml") -> list[ET.Element]:
    """Convenience function to get station info using default client"""
    client = FAAAPIClient()
    return client.get_station_info(airports, format)
