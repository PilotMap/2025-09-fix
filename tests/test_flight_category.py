#!/usr/bin/python3
"""
Unit tests for flight category calculation module.

Tests the compute_flight_category function with various scenarios including
missing flight_category tags, edge cases, and error conditions.
"""

import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
import sys
import os

# Add the parent directory to the path so we can import flight_category
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flight_category import compute_flight_category


class TestFlightCategory(unittest.TestCase):
    """Test cases for flight category calculation."""

    def setUp(self):
        """Set up test fixtures."""
        self.base_metar_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <response>
            <request_index>12345</request_index>
            <data_source name="metars"/>
            <request type="retrieve"/>
            <errors/>
            <warnings/>
            <time_taken_ms>123</time_taken_ms>
            <data num_results="1">
                <METAR>
                    <raw_text>KORD 041551Z 36010KT 10SM FEW250 15/03 A3012 RMK AO2 SLP201 T01500028</raw_text>
                    <station_id>KORD</station_id>
                    <observation_time>2023-10-04T15:51:00Z</observation_time>
                    <latitude>41.9786</latitude>
                    <longitude>-87.9048</longitude>
                    <temp_c>15</temp_c>
                    <dewpoint_c>3</dewpoint_c>
                    <wind_dir_degrees>360</wind_dir_degrees>
                    <wind_speed_kt>10</wind_speed_kt>
                    <visibility_statute_mi>10.0</visibility_statute_mi>
                    <altim_in_hg>30.12</altim_in_hg>
                    <sea_level_pressure_mb>1020.1</sea_level_pressure_mb>
                    <quality_control_flags>
                        <auto_station>TRUE</auto_station>
                    </quality_control_flags>
                    <sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>
                    <flight_category>VFR</flight_category>
                    <three_hr_pressure_tendency_mb>2.0</three_hr_pressure_tendency_mb>
                    <maxT_c>15.0</maxT_c>
                    <minT_c>2.8</minT_c>
                    <maxT24hr_c>15.0</maxT24hr_c>
                    <minT24hr_c>2.8</minT24hr_c>
                    <precip_in>0.00</precip_in>
                    <pcp3hr_in>0.00</pcp3hr_in>
                    <pcp6hr_in>0.00</pcp6hr_in>
                    <pcp24hr_in>0.00</pcp24hr_in>
                    <snow_in>0.0</snow_in>
                    <vert_vis_ft>25000</vert_vis_ft>
                    <metar_type>METAR</metar_type>
                    <elevation_m>201</elevation_m>
                </METAR>
            </data>
        </response>'''

    def create_metar_element(self, xml_content):
        """Helper method to create a METAR element from XML content."""
        root = ET.fromstring(xml_content)
        return root.find('.//METAR')

    def test_vfr_conditions(self):
        """Test VFR flight category calculation."""
        # VFR: ceiling > 3000 ft and visibility > 5 SM
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "VFR")

    def test_mvfr_conditions_ceiling(self):
        """Test MVFR flight category based on ceiling."""
        # MVFR: ceiling 1000-3000 ft
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="2000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")

    def test_mvfr_conditions_visibility(self):
        """Test MVFR flight category based on visibility."""
        # MVFR: visibility 3-5 SM
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>4.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")

    def test_ifr_conditions_ceiling(self):
        """Test IFR flight category based on ceiling."""
        # IFR: ceiling 500-1000 ft
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="800"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "IFR")

    def test_ifr_conditions_visibility(self):
        """Test IFR flight category based on visibility."""
        # IFR: visibility 1-3 SM
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>2.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "IFR")

    def test_lifr_conditions_ceiling(self):
        """Test LIFR flight category based on ceiling."""
        # LIFR: ceiling < 500 ft
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="400"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "LIFR")

    def test_lifr_conditions_visibility(self):
        """Test LIFR flight category based on visibility."""
        # LIFR: visibility < 1 SM
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>0.5</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "LIFR")

    def test_edge_case_3000_ft_ceiling(self):
        """Test edge case with exactly 3000 ft ceiling."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="3000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")

    def test_edge_case_5_sm_visibility(self):
        """Test edge case with exactly 5 SM visibility."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>5.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")

    def test_visibility_with_plus_prefix(self):
        """Test visibility parsing with '+' prefix."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>+10.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "VFR")

    def test_multiple_cloud_layers(self):
        """Test multiple cloud layers - should use lowest OVC/BKN/OVX."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '''<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>
            <sky_condition sky_cover="OVC" cloud_base_ft_agl="1500"/>
            <sky_condition sky_cover="BKN" cloud_base_ft_agl="8000"/>'''
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")  # Should use the 1500 ft OVC layer

    def test_vert_vis_ft_fallback(self):
        """Test fallback to vert_vis_ft when cloud_base_ft_agl is missing."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        ).replace(
            '<vert_vis_ft>25000</vert_vis_ft>',
            '<vert_vis_ft>1500</vert_vis_ft>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")

    def test_missing_visibility(self):
        """Test with missing visibility data."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="1500"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            ''
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")  # Should be based on ceiling only

    def test_missing_ceiling(self):
        """Test with missing ceiling data."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>2.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "IFR")  # Should be based on visibility only

    def test_missing_both_ceiling_and_visibility(self):
        """Test with missing both ceiling and visibility data."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            ''
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "NONE")  # NONE when no ceiling/visibility data

    def test_invalid_cloud_base_value(self):
        """Test with invalid cloud base value."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="OVC" cloud_base_ft_agl="invalid"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "NONE")

    def test_invalid_visibility_value(self):
        """Test with invalid visibility value."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>invalid</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "NONE")

    def test_sct_few_layers_do_not_set_ceiling(self):
        """Test that SCT/FEW layers don't set ceiling."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '''<sky_condition sky_cover="SCT" cloud_base_ft_agl="1000"/>
            <sky_condition sky_cover="FEW" cloud_base_ft_agl="2000"/>'''
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>2.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "IFR")  # Should be based on visibility only

    def test_forecast_field_available(self):
        """Test when forecast field is available."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            ''
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            ''
        ).replace(
            '</METAR>',
            '''<forecast>
                <sky_condition sky_cover="OVC" cloud_base_ft_agl="1500"/>
                <visibility_statute_mi>2.0</visibility_statute_mi>
            </forecast>
            </METAR>'''
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "IFR")

    def test_exception_handling(self):
        """Test exception handling with malformed XML."""
        # Create a malformed METAR element
        metar = ET.Element('METAR')
        station_id = ET.SubElement(metar, 'station_id')
        station_id.text = 'KORD'
        
        result = compute_flight_category(metar)
        self.assertEqual(result, "NONE")

    def test_fractional_visibility_values(self):
        """Test fractional visibility values."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>2.5</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "IFR")

    def test_very_high_visibility_values(self):
        """Test very high visibility values."""
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="4000"/>'
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>15.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "VFR")

    def test_ceiling_ordering_two_ovc_layers(self):
        """Test that the lowest OVC layer is selected when multiple OVC layers exist."""
        # Case with two OVC layers: OVC 8000 first, OVC 1500 second → expect MVFR
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '''<sky_condition sky_cover="OVC" cloud_base_ft_agl="8000"/>
            <sky_condition sky_cover="OVC" cloud_base_ft_agl="1500"/>'''
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "MVFR")  # Should use the 1500 ft OVC layer

    def test_ceiling_ordering_mixed_layers(self):
        """Test that the lowest BKN/OVC layer is selected regardless of order."""
        # Case with BKN 5000 first, OVC 400 later → expect LIFR
        xml = self.base_metar_xml.replace(
            '<flight_category>VFR</flight_category>', ''
        ).replace(
            '<sky_condition sky_cover="FEW" cloud_base_ft_agl="25000"/>',
            '''<sky_condition sky_cover="BKN" cloud_base_ft_agl="5000"/>
            <sky_condition sky_cover="OVC" cloud_base_ft_agl="400"/>'''
        ).replace(
            '<visibility_statute_mi>10.0</visibility_statute_mi>',
            '<visibility_statute_mi>6.0</visibility_statute_mi>'
        )
        
        metar = self.create_metar_element(xml)
        result = compute_flight_category(metar)
        self.assertEqual(result, "LIFR")  # Should use the 400 ft OVC layer


if __name__ == '__main__':
    unittest.main()
