# Publishing

This demo is developed here, but published elsewhere.

## Current setup

- Source files:
  - `demo/index.html`
  - `demo/app.css`
  - `demo/app.js`
- Generated demo data:
  - `demo/data/index.js`
  - `demo/data/chunks/`
  - `demo/data/names/`
- All these files together can be exported to / as a static website.

## Publish flow

1. Rebuild and copy the demo into the website repository:

   ```bash
   uv run python scripts/publish_demo.py <output-path>
   ```

2. Rebuild the website (if necessary, with Hugo for example):

3. Publish the website.

## Notes

- If only the HTML/CSS/JS changed and the generated data is still current, you can skip the export step:

  ```bash
  uv run python scripts/publish_demo.py <output-path> --skip-export
  ```
