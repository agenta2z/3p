/**
 * OpenStartup theme — re-exports from the shared theme module.
 *
 * This file exists so that `import ... from './theme'` resolves here
 * (which takes precedence over the `theme/` directory).  We re-export
 * the full public API so every consumer gets the same surface.
 */
export { default } from './theme/themes/dark';
export {
  AppThemeProvider,
  useAppTheme,
  ThemeSwitcher,
  createAppTheme,
  getTheme,
  listThemes,
  registerTheme,
  mergeTheme,
  applyCssVariables,
} from './theme/index';
