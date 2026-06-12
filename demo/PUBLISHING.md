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
   uv run qq publish-demo <output-path>
   ```

2. Rebuild the website (if necessary, with Hugo for example):

3. Publish the website.

## Notes

- If only the HTML/CSS/JS changed and the generated data is still current, you can skip the export step:

  ```bash
  uv run qq publish-demo <output-path> --skip-export
  ```

- If the output directory already exists, the command asks before replacing it. For automated publishing, pass `--yes`:

  ```bash
  uv run qq publish-demo <output-path> --yes
  ```
