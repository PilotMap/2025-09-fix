#!/usr/bin/python3
"""
Flight Category Calculation Module

This module provides shared flight category calculation logic for METAR data
when the Aviation Weather API doesn't provide flight_category tags.

The module implements standard FAA flight category thresholds:
- VFR: ceiling > 3000 ft and visibility > 5 SM
- MVFR: ceiling 1000-3000 ft and/or visibility 3-5 SM  
- IFR: ceiling 500-1000 ft and/or visibility 1-3 SM
- LIFR: ceiling < 500 ft and/or visibility < 1 SM
- NONE: invalid/missing data or when both ceiling and visibility data are unavailable

Key Features:
- Automatically selects the lowest OVC/BKN/OVX layer as ceiling
- Falls back to vertical visibility when no OVC/BKN/OVX layers exist
- Supports both METAR and forecast data structures
- Graceful error handling with fallback to visibility-only classification
- Returns NONE only when both ceiling and visibility data are invalid/missing

Default Behavior:
When both ceiling and visibility data are missing or invalid, the function returns "NONE"
to ensure LEDs display the appropriate "no weather" color rather than defaulting to VFR.

Author: Based on contribution by Nick Cirincione
"""

import logging

logger = logging.getLogger(__name__)


def compute_flight_category(metar_elem):
    """
    Calculate flight category from METAR XML element when flight_category is missing.
    
    This function implements FAA flight category thresholds based on ceiling and visibility.
    It automatically selects the lowest OVC/BKN/OVX layer as the ceiling and falls back
    to vertical visibility when no such layers exist. Supports both METAR and forecast
    data structures.
    
    Args:
        metar_elem: XML element containing METAR data
        
    Returns:
        str: Flight category (VFR/MVFR/IFR/LIFR/NONE)
        
    Behavior:
        - VFR: ceiling > 3000 ft and visibility > 5 SM
        - MVFR: ceiling 1000-3000 ft and/or visibility 3-5 SM
        - IFR: ceiling 500-1000 ft and/or visibility 1-3 SM
        - LIFR: ceiling < 500 ft and/or visibility < 1 SM
        - NONE: when both ceiling and visibility data are invalid/missing
        
    The function uses graceful error handling - if ceiling data is invalid, it continues
    with visibility-only classification. Only returns NONE when both data sources fail.
    """
    try:
        station_id = metar_elem.find('station_id')
        station_id = station_id.text if station_id is not None else "UNKNOWN"
        
        logger.info(f"{station_id} Computing flight category from visibility and ceiling data")
        
        flightcategory = "VFR"  # Initialize flight category (will be overridden by data if available)
        sky_cvr = "SKC"  # Initialize to Sky Clear
        
        # Check if forecast field is available, otherwise use sky_condition
        forecast_elem = metar_elem.find('forecast')
        if forecast_elem is None:
            logger.info('FAA xml data is NOT providing the forecast field for this airport')
            sky_conditions = metar_elem.findall('./sky_condition')
        else:
            logger.info('FAA xml data IS providing the forecast field for this airport')
            sky_conditions = metar_elem.findall('./forecast/sky_condition')
        
        # Set visibility element based on whether forecast is present
        visibility_elem = forecast_elem.find('visibility_statute_mi') if forecast_elem is not None else metar_elem.find('visibility_statute_mi')
        
        # Build a list of bases from OVC, BKN, or OVX layers
        bases = []
        for sky_condition in sky_conditions:
            sky_cvr = sky_condition.attrib['sky_cover']
            logger.debug(f'Sky Cover = {sky_cvr}')
            
            if sky_cvr in ("OVC", "BKN", "OVX"):
                try:
                    cloud_base_ft_agl = sky_condition.attrib['cloud_base_ft_agl']
                    if cloud_base_ft_agl is not None:
                        bases.append(int(cloud_base_ft_agl))
                except (KeyError, ValueError, TypeError):
                    # Skip this layer if cloud_base_ft_agl is missing or invalid
                    continue
        
        # Set flight category based on cloud ceiling
        if bases:
            cld_base_ft_agl = min(bases)
            logger.debug(f'Lowest cloud base = {cld_base_ft_agl}')
        else:
            # Fallback to vertical visibility if no OVC/BKN/OVX layers found
            try:
                vert_vis_elem = metar_elem.find('vert_vis_ft')
                if vert_vis_elem is not None:
                    cld_base_ft_agl = int(vert_vis_elem.text)
                    logger.debug(f'Using vertical visibility as ceiling = {cld_base_ft_agl}')
                else:
                    logger.warning(f"{station_id}: No cloud base or vertical visibility data available")
                    cld_base_ft_agl = None
            except (ValueError, TypeError) as e:
                logger.error(f"{station_id}: Error getting vertical visibility: {e}")
                cld_base_ft_agl = None
        
        if cld_base_ft_agl is not None:
            try:
                logger.debug(f'Cloud Base = {cld_base_ft_agl}')
                
                if cld_base_ft_agl < 500:
                    flightcategory = "LIFR"
                elif 500 <= cld_base_ft_agl < 1000:
                    flightcategory = "IFR"
                elif 1000 <= cld_base_ft_agl <= 3000:
                    flightcategory = "MVFR"
                elif cld_base_ft_agl > 3000:
                    flightcategory = "VFR"
            except (ValueError, TypeError) as e:
                logger.error(f"{station_id}: Invalid cloud base value '{cld_base_ft_agl}': {e}")
                cld_base_ft_agl = None
        
        # Check visibility if not already LIFR due to ceiling
        if flightcategory != "LIFR":
            if visibility_elem is not None:
                try:
                    visibility_statute_mi = visibility_elem.text
                    visibility_statute_mi = float(visibility_statute_mi.strip('+'))
                    logger.debug(f'Visibility = {visibility_statute_mi} SM')
                    
                    if visibility_statute_mi < 1.0:
                        flightcategory = "LIFR"
                    elif 1.0 <= visibility_statute_mi < 3.0:
                        flightcategory = "IFR"
                    elif 3.0 <= visibility_statute_mi <= 5.0 and flightcategory != "IFR":
                        # If Flight Category was already set to IFR by clouds, it can't be reduced to MVFR
                        flightcategory = "MVFR"
                except (ValueError, TypeError) as e:
                    logger.error(f"{station_id}: Invalid visibility value '{visibility_elem.text}': {e}")
                    # Skip visibility-based adjustments, don't change flightcategory
            else:
                logger.warning(f"{station_id}: No visibility data available")
        
        # Only return NONE if both ceiling and visibility could not be parsed
        # Check if we have any valid data to work with
        has_valid_ceiling = cld_base_ft_agl is not None
        has_valid_visibility = visibility_elem is not None and visibility_elem.text is not None
        
        if not has_valid_ceiling and not has_valid_visibility:
            logger.warning(f"{station_id}: No valid ceiling or visibility data available")
            return "NONE"
        
        logger.debug(f"{station_id} flight category is calculated as {flightcategory}")
        return flightcategory
        
    except Exception as e:
        logger.error(f"Error computing flight category: {e}")
        return "NONE"
