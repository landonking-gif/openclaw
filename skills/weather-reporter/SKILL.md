# weather-reporter

Fetch current weather data for any city using the wttr.in free API.

## Usage

```bash
python scripts/get_weather.py "City Name"
```

## Examples

```bash
python scripts/get_weather.py "San Francisco"
python scripts/get_weather.py "London"
python scripts/get_weather.py "Tokyo"
```

## Output

Returns JSON with:
- `city`: City name
- `temperature`: Current temperature with unit
- `condition`: Weather condition
- `humidity`: Humidity percentage
- `wind`: Wind speed

## API

Uses wttr.in — free, no API key required.
