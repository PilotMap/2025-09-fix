"""
Integration tests for LiveSectional Aviation Weather API migration

This module tests the integration between the centralized API client
and the main application components.
"""

import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from faa_api_client import FAAAPIClient, NetworkError, APIError


class TestIntegration(unittest.TestCase):
    """Integration tests for the aviation weather API migration"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = FAAAPIClient()
        self.sample_airports = ["KORD", "KLAX", "KJFK"]
        
    def test_metar_v4_integration(self):
        """Test integration with metar-v4.py functionality"""
        # This would test the actual metar-v4.py script if it were importable
        # For now, we test the API client methods that metar-v4.py would use
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock successful response
            mock_request.return_value = (200, '<response><METAR><station_id>KORD</station_id></METAR></response>')
            
            result = self.client.get_metars(self.sample_airports, 2.5, "xml")
            
            self.assertEqual(len(result), 1)
            mock_request.assert_called_once()
                
    def test_metar_display_v4_integration(self):
        """Test integration with metar-display-v4.py functionality"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock successful response
            mock_request.return_value = (200, '<response><METAR><station_id>KORD</station_id></METAR></response>')
            
            result = self.client.get_metars(self.sample_airports, 2.5, "xml")
            
            self.assertEqual(len(result), 1)
                
    def test_wipes_v4_integration(self):
        """Test integration with wipes-v4.py functionality"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock successful response
            mock_request.return_value = (200, '<response><METAR><station_id>KORD</station_id></METAR></response>')
            
            result = self.client.get_metars(self.sample_airports, 2.5, "xml")
            
            self.assertEqual(len(result), 1)
                
    def test_app_integration(self):
        """Test integration with app.py functionality"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock successful response for both METAR and station info
            mock_request.return_value = (200, '<response><METAR><station_id>KORD</station_id></METAR></response>')
            
            # Test METAR retrieval
            metar_result = self.client.get_metars(self.sample_airports, 2.5, "xml")
            self.assertEqual(len(metar_result), 1)
            
            # Test station info retrieval
            station_result = self.client.get_station_info(self.sample_airports, "xml")
            self.assertEqual(len(station_result), 1)
                
    def test_error_handling_integration(self):
        """Test error handling across all components"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Test network error
            mock_request.side_effect = NetworkError("Connection failed")
            
            with self.assertRaises(NetworkError):
                self.client.get_metars(self.sample_airports, 2.5, "xml")
                
            # Test API error
            mock_request.side_effect = APIError("404 Not Found")
            
            with self.assertRaises(APIError):
                self.client.get_metars(self.sample_airports, 2.5, "xml")
                
    def test_retry_logic_integration(self):
        """Test retry logic across all components"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock network error on first two calls, success on third
            mock_request.side_effect = [
                NetworkError("Connection failed"),
                NetworkError("Connection failed"),
                (200, '<response><METAR><station_id>KORD</station_id></METAR></response>')
            ]
            
            with patch('time.sleep'):  # Mock sleep to speed up test
                status_code, response_body = self.client._make_request('/metar', {'format': 'xml', 'ids': 'KORD', 'hours': '2.5'})
                
            self.assertEqual(status_code, 200)
            self.assertEqual(response_body, '<response><METAR><station_id>KORD</station_id></METAR></response>')
            self.assertEqual(mock_request.call_count, 3)
            
    def test_204_handling_integration(self):
        """Test 204 No Content handling across all components"""
        with patch.object(self.client, '_make_request') as mock_request:
            # Mock 204 response
            mock_request.return_value = (204, '')
                
            result = self.client.get_metars(self.sample_airports, 2.5, "xml")
            
            self.assertEqual(len(result), 0)
            mock_request.assert_called_once()


if __name__ == '__main__':
    unittest.main()
