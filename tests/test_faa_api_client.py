"""
Unit tests for FAA API Client

This module tests the centralized aviation weather API client functionality,
including error handling, retry logic, and XML parsing.
"""

import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch, MagicMock, mock_open
import urllib.error
import json
import os
import sys

# Add parent directory to path to import faa_api_client
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faa_api_client import FAAAPIClient, NetworkError, APIError, AviationWeatherAPIError


class TestFAAAPIClient(unittest.TestCase):
    """Test cases for FAAAPIClient class"""
    
    def setUp(self):
        """Set up test fixtures before each test method"""
        self.client = FAAAPIClient()
        self.sample_airports = ["KORD", "KLAX", "KJFK"]
        
    def test_init_default_values(self):
        """Test client initialization with default values"""
        client = FAAAPIClient()
        self.assertEqual(client.base_url, "https://aviationweather.gov/api/data")
        self.assertEqual(client.timeout, 30)
        self.assertEqual(client.max_retries, 3)
        self.assertEqual(client.retry_delay, 1.0)
        
    def test_init_custom_values(self):
        """Test client initialization with custom values"""
        client = FAAAPIClient(
            base_url="https://test.example.com",
            timeout=60,
            max_retries=5,
            retry_delay=10
        )
        self.assertEqual(client.base_url, "https://test.example.com")
        self.assertEqual(client.timeout, 60)
        self.assertEqual(client.max_retries, 5)
        self.assertEqual(client.retry_delay, 10)
        
    def test_make_request_url_building(self):
        """Test URL building for METAR requests"""
        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.getcode.return_value = 200
            mock_response.read.return_value = b'<response></response>'
            mock_urlopen.return_value.__enter__.return_value = mock_response
            
            self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD,KLAX,KJFK', 'hours': '2.5'})
            
            # Verify the URL was constructed correctly
            call_args = mock_urlopen.call_args[0][0]
            self.assertIn('https://aviationweather.gov/api/data/metar', call_args.full_url)
            self.assertIn('format=xml', call_args.full_url)
            self.assertIn('ids=KORD,KLAX,KJFK', call_args.full_url)
            self.assertIn('hours=2.5', call_args.full_url)
        
    @patch('urllib.request.urlopen')
    def test_make_request_success(self, mock_urlopen):
        """Test successful API request"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'<response><METAR><station_id>KORD</station_id></METAR></response>'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        status_code, response_body = self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
        
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, '<response><METAR><station_id>KORD</station_id></METAR></response>')
        mock_urlopen.assert_called_once()
        
    @patch('urllib.request.urlopen')
    def test_make_request_204_no_content(self, mock_urlopen):
        """Test 204 No Content response handling"""
        # Mock 204 response
        mock_response = MagicMock()
        mock_response.getcode.return_value = 204
        mock_response.read.return_value = b''
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        status_code, response_body = self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
        
        self.assertEqual(status_code, 204)
        self.assertEqual(response_body, '')
        mock_urlopen.assert_called_once()
        
    @patch('urllib.request.urlopen')
    def test_make_request_404_error(self, mock_urlopen):
        """Test 404 error handling"""
        # Mock 404 response
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://test.example.com", 404, "Not Found", {}, None
        )
        
        with self.assertRaises(APIError) as context:
            self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
            
        self.assertIn("404", str(context.exception))
        
    @patch('urllib.request.urlopen')
    def test_make_request_500_error(self, mock_urlopen):
        """Test 500 error handling"""
        # Mock 500 response
        mock_urlopen.side_effect = urllib.error.HTTPError(
            "https://test.example.com", 500, "Internal Server Error", {}, None
        )
        
        with self.assertRaises(APIError) as context:
            self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
            
        self.assertIn("500", str(context.exception))
        
    @patch('urllib.request.urlopen')
    def test_make_request_network_error(self, mock_urlopen):
        """Test network error handling"""
        # Mock network error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        with self.assertRaises(NetworkError) as context:
            self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
            
        self.assertIn("Connection refused", str(context.exception))
        
    @patch('urllib.request.urlopen')
    def test_make_request_timeout_error(self, mock_urlopen):
        """Test timeout error handling"""
        # Mock timeout error
        mock_urlopen.side_effect = urllib.error.URLError("timed out")
        
        with self.assertRaises(NetworkError) as context:
            self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
            
        self.assertIn("timed out", str(context.exception))
        
    @patch('urllib.request.urlopen')
    def test_make_request_retry_logic(self, mock_urlopen):
        """Test retry logic on network errors"""
        # Mock network error on first two calls, success on third
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = b'<response></response>'
        
        mock_urlopen.side_effect = [
            urllib.error.URLError("Connection refused"),
            urllib.error.URLError("Connection refused"),
            mock_response
        ]
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            status_code, response_body = self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
            
        self.assertEqual(status_code, 200)
        self.assertEqual(response_body, '<response></response>')
        self.assertEqual(mock_urlopen.call_count, 3)
        
    @patch('urllib.request.urlopen')
    def test_make_request_max_retries_exceeded(self, mock_urlopen):
        """Test max retries exceeded"""
        # Mock persistent network error
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")
        
        with patch('time.sleep'):  # Mock sleep to speed up test
            with self.assertRaises(NetworkError):
                self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
                
        self.assertEqual(mock_urlopen.call_count, 4)  # Initial + 3 retries
        
    def test_parse_xml_valid(self):
        """Test XML parsing with valid response"""
        xml_data = '<response><METAR><station_id>KORD</station_id><flight_category>VFR</flight_category></METAR></response>'
        result = self.client._parse_xml(xml_data)
        
        self.assertEqual(result.tag, 'response')
        metar = result.find('METAR')
        self.assertEqual(metar.find('station_id').text, 'KORD')
        self.assertEqual(metar.find('flight_category').text, 'VFR')
        
    def test_parse_xml_empty(self):
        """Test XML parsing with empty response"""
        xml_data = '<response></response>'
        result = self.client._parse_xml(xml_data)
        
        self.assertEqual(result.tag, 'response')
        
    def test_parse_xml_invalid(self):
        """Test XML parsing with invalid XML"""
        xml_data = '<invalid xml>'
        
        with self.assertRaises(APIError) as context:
            self.client._parse_xml(xml_data)
            
        self.assertIn("Failed to parse XML", str(context.exception))
        
    @patch.object(FAAAPIClient, '_make_request')
    def test_get_metars_success(self, mock_request):
        """Test successful METAR retrieval"""
        # Mock response
        mock_request.return_value = (200, '<response><METAR><station_id>KORD</station_id></METAR></response>')
        
        result = self.client.get_metars(self.sample_airports, 2.5, "xml")
        
        self.assertEqual(len(result), 1)
        mock_request.assert_called_once()
        
    @patch.object(FAAAPIClient, '_make_request')
    def test_get_metars_network_error(self, mock_request):
        """Test METAR retrieval with network error"""
        mock_request.side_effect = NetworkError("Connection failed")
        
        with self.assertRaises(NetworkError):
            self.client.get_metars(self.sample_airports, 2.5, "xml")
            
    @patch.object(FAAAPIClient, '_make_request')
    def test_get_metars_api_error(self, mock_request):
        """Test METAR retrieval with API error"""
        mock_request.side_effect = APIError("404 Not Found")
        
        with self.assertRaises(APIError):
            self.client.get_metars(self.sample_airports, 2.5, "xml")
            
    @patch.object(FAAAPIClient, '_make_request')
    def test_get_tafs_success(self, mock_request):
        """Test successful TAF retrieval"""
        mock_request.return_value = (200, '<response><TAF><station_id>KORD</station_id></TAF></response>')
        
        result = self.client.get_tafs(self.sample_airports, 6, "xml")
        
        self.assertEqual(len(result), 1)
        mock_request.assert_called_once()
        
    @patch.object(FAAAPIClient, '_make_request')
    def test_get_station_info_success(self, mock_request):
        """Test successful station info retrieval"""
        mock_request.return_value = (200, '<response><Station><station_id>KORD</station_id></Station></response>')
        
        result = self.client.get_station_info(self.sample_airports, "xml")
        
        self.assertEqual(len(result), 1)
        mock_request.assert_called_once()
        
    def test_chunk_airports(self):
        """Test airport chunking functionality"""
        large_airport_list = [f"K{i:03d}" for i in range(500)]
        chunks = self.client._chunk_airports(large_airport_list, chunk_size=300)
        
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0]), 300)
        self.assertEqual(len(chunks[1]), 200)
        
    def test_chunk_airports_empty(self):
        """Test airport chunking with empty list"""
        chunks = self.client._chunk_airports([])
        self.assertEqual(len(chunks), 0)


class TestExceptionHierarchy(unittest.TestCase):
    """Test exception class hierarchy"""
    
    def test_exception_inheritance(self):
        """Test that custom exceptions inherit properly"""
        self.assertTrue(issubclass(NetworkError, AviationWeatherAPIError))
        self.assertTrue(issubclass(APIError, AviationWeatherAPIError))
        
    def test_exception_instantiation(self):
        """Test exception instantiation"""
        network_error = NetworkError("Connection failed")
        api_error = APIError("404 Not Found")
        base_error = AviationWeatherAPIError("Generic error")
        
        self.assertEqual(str(network_error), "Connection failed")
        self.assertEqual(str(api_error), "404 Not Found")
        self.assertEqual(str(base_error), "Generic error")


if __name__ == '__main__':
    unittest.main()
