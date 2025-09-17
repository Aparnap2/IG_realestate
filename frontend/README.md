// README.md
# AAA Real Estate Lead Capture Agentic AI System - Frontend

This is the frontend for the AAA Real Estate Lead Capture Agentic AI System, built with React, Vite, and shadcn/ui components.

## Features

- Real-time lead monitoring dashboard
- Property management (add, view, update, delete)
- Configuration management for agent prompts
- User authentication with Supabase

## Tech Stack

- React 18 with TypeScript
- Vite for fast development and building
- shadcn/ui components with Tailwind CSS
- Supabase for backend services
- React Query for server state management

## Setup Instructions

### Prerequisites

- Node.js 18+
- pnpm package manager

### Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   pnpm install
   ```

3. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Supabase credentials
   ```

4. Run the development server:
   ```bash
   pnpm run dev
   ```

## Project Structure

```
src/
├── components/     # React components
│   └── ui/         # shadcn/ui components
├── hooks/          # Custom React hooks
├── lib/            # Utility functions and Supabase client
└── App.tsx         # Main application component
```

## Development

### Adding New Components

1. Create new components in `src/components/`
2. Use shadcn/ui components when possible for consistency
3. Follow the existing patterns for props and TypeScript interfaces

### Styling

- Use Tailwind CSS classes for styling
- Follow the existing color scheme and design patterns
- Use shadcn/ui components for consistent UI elements

## Building for Production

```bash
pnpm run build
```

The built files will be in the `dist/` directory.

## Deployment

The frontend can be deployed to any static hosting service (Vercel, Netlify, etc.) or served through the backend.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request