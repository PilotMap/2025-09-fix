# Aviation Weather API Migration Documentation

## Overview

This document describes the migration of LiveSectional from the legacy ADDS dataserver to the new Aviation Weather API. The migration focuses on robustness improvements, error handling, and centralized API management.

## Changes Made

### 1. Centralized API Client (`faa_api_client.py`)

**New Features:**
- Unified interface for all aviation weather API calls
- Comprehensive error handling with custom exception hierarchy
- Automatic retry logic with exponential backoff
- 204 No Content response handling
- XML parsing with proper error handling
- Airport code validation
- Configurable timeouts and retry parameters

**Key Classes:**
- `FAAAPIClient`: Main client class
- `AviationWeatherAPIError`: Base exception class
- `NetworkError`: Network-related errors
- `APIError`: API-related errors (4xx, 5xx status codes)

### 2. Updated Python Scripts

**Files Modified:**
- `metar-v4.py`: Updated to use centralized API client
- `metar-display-v4.py`: Updated to use centralized API client  
- `wipes-v4.py`: Updated to use centralized API client
- `app.py`: Updated `get_led_map_info()` and `get_apinfo()` functions

**Key Changes:**
- Replaced direct URL construction with API client calls
- Improved error handling with specific exception types
- Removed manual XML wrapper construction
- Added proper 204 No Content handling
- Centralized retry logic

### 3. Frontend JavaScript Updates (`templates/base.html`)

**Functions Updated:**
- `get_badge()`: Now uses aviation weather API instead of NWS API
- `get_raw()`: Now uses aviation weather API instead of NWS API

**Key Changes:**
- Switched from JSON to XML parsing
- Updated API endpoints to use aviationweather.gov
- Improved error handling for missing data
- Maintained backward compatibility with existing UI

### 4. Testing Infrastructure

**New Test Files:**
- `tests/test_faa_api_client.py`: Unit tests for API client
- `tests/test_integration.py`: Integration tests
- `tests/fixtures/`: Sample API responses for testing

**Test Coverage:**
- API client functionality
- Error handling scenarios
- Retry logic
- XML parsing
- Integration with existing components

## API Endpoints Used

### METAR Data
- **Endpoint**: `https://aviationweather.gov/api/data/metar`
- **Parameters**: `format=xml&hours=2.5&ids=AIRPORT_CODES`
- **Response**: XML with METAR observations

### TAF Data  
- **Endpoint**: `https://aviationweather.gov/api/data/taf`
- **Parameters**: `format=xml&hours=6&ids=AIRPORT_CODES`
- **Response**: XML with TAF forecasts

### Station Information
- **Endpoint**: `https://aviationweather.gov/api/data/stationinfo`
- **Parameters**: `format=xml&ids=AIRPORT_CODES`
- **Response**: XML with station details

## Error Handling

### HTTP Status Codes
- **200**: Success with data
- **204**: Success with no data (treated as valid empty response)
- **4xx**: Client errors (APIError)
- **5xx**: Server errors (APIError)
- **Network errors**: Connection issues (NetworkError)

### Retry Logic
- **Max retries**: 3 (configurable)
- **Retry delay**: 1.0 seconds (configurable)
- **Retry conditions**: Network errors and 5xx server errors
- **No retry**: API errors (4xx)

## Configuration

### API Client Settings
```python
client = FAAAPIClient(
    base_url="https://aviationweather.gov/api/data",
    timeout=30,
    max_retries=3,
    retry_delay=1.0
)
```

### Environment Variables
- No additional environment variables required
- All configuration handled through code

## Migration Benefits

### 1. Robustness
- Centralized error handling
- Automatic retry logic
- Proper 204 No Content handling
- Network error recovery

### 2. Maintainability
- Single source of truth for API calls
- Consistent error handling across components
- Easier to update API endpoints
- Centralized configuration

### 3. Reliability
- Better error reporting
- Improved logging
- Graceful degradation
- Reduced API call failures

### 4. Testing
- Comprehensive test coverage
- Mock API responses
- Integration testing
- Error scenario testing

## Backward Compatibility

### Maintained Features
- All existing functionality preserved
- Same data structures returned
- Compatible with existing configuration
- No breaking changes to user interface

### Deprecated Features
- Legacy ADDS dataserver URLs (commented out)
- Manual XML wrapper construction
- Generic exception handling
- Inconsistent error reporting

## Usage Examples

### Basic METAR Retrieval
```python
from faa_api_client import FAAAPIClient

client = FAAAPIClient()
metars = client.get_metars(["KORD", "KLAX"], 2.5, "xml")
```

### Error Handling
```python
from faa_api_client import FAAAPIClient, NetworkError, APIError

client = FAAAPIClient()
try:
    metars = client.get_metars(["KORD"], 2.5, "xml")
except NetworkError as e:
    print(f"Network error: {e}")
except APIError as e:
    print(f"API error: {e}")
```

### Custom Configuration
```python
client = FAAAPIClient(
    timeout=60,
    max_retries=5,
    retry_delay=10
)
```

## Testing

### Running Tests
```bash
# Run all tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=faa_api_client

# Run specific test file
python -m pytest tests/test_faa_api_client.py
```

### Test Structure
- **Unit tests**: Test individual components
- **Integration tests**: Test component interactions
- **Fixtures**: Sample API responses
- **Mocking**: Network calls and external dependencies

## Troubleshooting

### Common Issues

1. **Network Errors**
   - Check internet connectivity
   - Verify API endpoint availability
   - Check firewall settings

2. **API Errors**
   - Verify airport codes are valid
   - Check API rate limits
   - Review error messages in logs

3. **XML Parsing Errors**
   - Check API response format
   - Verify XML structure
   - Review error logs

### Debugging

1. **Enable Debug Logging**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check API Responses**
   - Review network traffic
   - Log API responses
   - Verify XML structure

3. **Test Individual Components**
   - Run unit tests
   - Test API client directly
   - Verify error handling

## Future Enhancements

### Planned Improvements
- Caching for API responses
- Rate limiting
- Metrics collection
- Performance monitoring
- Additional error recovery strategies

### API Updates
- Monitor for API changes
- Update endpoints as needed
- Maintain backward compatibility
- Test with new API versions

## Support

### Documentation
- This migration guide
- API client documentation
- Test documentation
- Code comments

### Issues
- Check error logs
- Review test results
- Verify configuration
- Test with sample data

### Updates
- Monitor API changes
- Update dependencies
- Test new features
- Maintain compatibility
