import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { RouterProvider } from 'react-router';
import '@fontsource-variable/geist';
import '@fontsource-variable/geist-mono';
import './styles/tokens.css';
import './styles/base.css';
import { createQueryClient, Providers } from './App';
import { createRouter } from './routes/router';

const root = document.getElementById('root');
if (!root) throw new Error('The page has no #root element.');

createRoot(root).render(
  <StrictMode>
    <Providers client={createQueryClient()}>
      <RouterProvider router={createRouter()} />
    </Providers>
  </StrictMode>,
);
