/**
 * theme/index.js — re-exports from @agent-foundation/shared-ui/theme.
 *
 * The canonical theme module now lives in the shared library.
 * OpenStartup-specific themes (openstartup) are registered at app bootstrap.
 */

export { AppThemeProvider, useAppTheme } from './ThemeProvider';
export { default as ThemeSwitcher } from './ThemeSwitcher';
export { default as createAppTheme } from './createAppTheme';
export { getTheme, listThemes, registerTheme } from './themeRegistry';
export { applyCssVariables } from './cssVariableBridge';

// Register OpenStartup-specific theme
import { registerTheme } from './themeRegistry';
const openstartupTheme = {
  id: 'openstartup',
  name: 'OpenStartup',
  extends: 'dark',
  palette: {
    primary: { main: '#00bcd4', light: '#4dd0e1', dark: '#00838f' },
  },
};
try { registerTheme('openstartup', openstartupTheme); } catch (e) { /* already registered */ }
