import React from 'react';
import ReactDOM from 'react-dom/client';
import { createTheme } from '@mui/material/styles';
import { AppThemeProvider, registerTheme } from './theme';
import App from './App';
import './App.css';

// Task 8.11: Register custom OpenStartup brand theme (teal primary, extends dark)
registerTheme('openstartup', {
  id: 'openstartup',
  name: 'OpenStartup',
  extends: 'dark',
  palette: {
    primary: { main: '#00bcd4', light: '#4dd0e1', dark: '#00838f' },
  },
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <AppThemeProvider createThemeFn={createTheme} defaultThemeId="dark">
      <App />
    </AppThemeProvider>
  </React.StrictMode>
);
