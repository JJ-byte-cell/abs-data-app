# Australian Macro Dashboard — Financial Terminal Theme

Visual redesign of the existing dashboard. Original charts, datasets, filters, calculations, data requests, and research modules remain in place.

## Deploy

Copy **app.py**, **macro_research.py**, **terminal_tooltips.py**, **terminal_theme.py**, **requirements.txt**, and the **.streamlit/config.toml** file to your repository. Replace existing files of the same name; preserve other files. In Streamlit Cloud, ensure the main file is `app.py`.

The `.streamlit/config.toml` file is important for a dark appearance across Streamlit widgets. `terminal_theme.py` applies additional CSS styling. `terminal_tooltips.py` applies chart and hover styling at render time.

## Notes

- No ABS/RBA API or calculation logic was changed.
- Chart formatting is applied at render time; existing data is not modified.
- Some Streamlit widgets and Plotly toolbar elements are controlled by framework versions and may vary slightly.
- Source requests and browser rendering were not live-tested; Python syntax was checked.
