# YouTube Feed Aggregator - Frontend

A dark, minimal, responsive React SPA for viewing and filtering YouTube RSS feeds from your subscriptions.

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling with dark-first design
- **React Router** - Client-side routing

## Features

- Google OAuth authentication
- Grid and list view toggle
- Channel filtering sidebar
- Cursor-based pagination
- Responsive design (320px - 1920px)
- Dark theme with clean aesthetic
- YouTube video embeds
- Real-time subscription sync

## Development

### Prerequisites

- Node.js 18+ or Bun
- Backend API running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install
# or
bun install
```

### Running the Dev Server

```bash
# Start development server on http://localhost:3000
npm run dev
# or
bun run dev
```

The dev server is configured with a proxy that forwards:
- `/api/*` requests to `http://localhost:8000`
- `/auth/*` requests to `http://localhost:8000`

### Building for Production

```bash
# Build static files to dist/
npm run build
# or
bun run build
```

### Preview Production Build

```bash
# Preview the production build locally
npm run preview
# or
bun run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts          # API wrapper for backend calls
│   ├── pages/
│   │   ├── Login.tsx           # Login page (redirects to OAuth)
│   │   └── Feed.tsx            # Main feed page
│   ├── components/
│   │   ├── VideoCard.tsx       # Individual video card with iframe embed
│   │   ├── ChannelSidebar.tsx  # Sidebar with channel list and filtering
│   │   ├── Pagination.tsx      # Pagination controls with cursor
│   │   └── ViewToggle.tsx      # Grid/List view toggle
│   ├── App.tsx                 # Main app component with routing
│   ├── main.tsx                # Entry point
│   └── index.css               # Global styles and Tailwind imports
├── index.html
├── vite.config.ts
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
└── package.json
```

## API Integration

The frontend communicates with the backend via the following endpoints:

- `GET /auth/login` - Initiate OAuth flow
- `POST /auth/logout` - Clear session
- `GET /auth/me` - Get current user
- `GET /api/subscriptions` - List subscribed channels
- `POST /api/subscriptions/refresh` - Sync from YouTube
- `GET /api/feed?limit=24&cursor=...&channel_id=...` - Get feed items

Authentication is handled via HTTPOnly cookies automatically sent with requests.

## Environment

The frontend assumes the backend is running on `http://localhost:8000` during development.

For production, you'll need to:
1. Build the frontend: `npm run build`
2. Serve the `dist/` folder from your web server
3. Configure your backend to allow CORS from your frontend domain
4. Set `FRONTEND_ORIGIN` in backend `.env` to your frontend domain

## Design

- **Dark-first**: Uses `dark` class on `<html>` element
- **Neutral palette**: bg-neutral-900, bg-neutral-800, etc.
- **Responsive grid**: 1-4 columns based on screen size
- **Clean typography**: System fonts with good readability
- **Smooth transitions**: Hover states and loading indicators
