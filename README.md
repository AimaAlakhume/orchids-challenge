# Orchids SWE Intern Challenge Template

This project consists of a backend built with FastAPI and a frontend built with Next.js and TypeScript.

## Backend

The backend uses `uv` for package management.

### Installation

To install the backend dependencies, run the following command in the backend project directory:

```bash
uv sync
```

### Running the Backend

To run the backend development server, use the following command:

```bash
uv run fastapi dev
```

## Frontend

The frontend is built with Next.js and TypeScript.

### Installation

To install the frontend dependencies, navigate to the frontend project directory and run:

```bash
npm install
```

### Running the Frontend

To start the frontend development server, run:

```bash
npm run dev
```
## Additional Setup Instructions

1. Install backend dependencies
```bash
pip install fastapi uvicorn playwright httpx beautifulsoup4 python-dotenv anthropic
```

2. Install Playwright Browsers
```bash
bashplaywright install chromium
```

3. Environment Configuration
Create a .env file in the root directory with an Anthropic API key:
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```
4. Create Required Directories
Create a public directory to serve screenshots.
```bash
bashmkdir -p public/screenshots
```
