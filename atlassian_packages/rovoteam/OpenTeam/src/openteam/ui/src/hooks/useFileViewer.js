/**
 * useFileViewer — manages state for the right-panel file viewer drawer.
 *
 * Fetches file content from /api/view/{path} and manages open/close state.
 * Used by ManagerChatView to open role documents, research outputs, etc.
 */

import { useState, useCallback } from 'react';

export function useFileViewer() {
  const [fileViewerOpen, setFileViewerOpen] = useState(false);
  const [fileContent, setFileContent] = useState('');
  const [fileName, setFileName] = useState('');
  const [fileError, setFileError] = useState(null);
  const [fileLoading, setFileLoading] = useState(false);

  // Folder browsing state
  const [folderTree, setFolderTree] = useState(null);
  const [folderPath, setFolderPath] = useState('');
  const [isFolderMode, setIsFolderMode] = useState(false);
  const [selectedFilePath, setSelectedFilePath] = useState('');

  const openFileViewer = useCallback(async (filePath) => {
    if (!filePath) return;
    setFileError(null);
    setFileContent('');
    setFileLoading(true);
    setIsFolderMode(false);
    setFolderTree(null);
    setFileViewerOpen(true);

    try {
      const name = filePath.split('/').pop() || 'Document';
      setFileName(name);

      const response = await fetch(`/api/view/${filePath}`);
      if (!response.ok) {
        const msg = await response.text().catch(() => `HTTP ${response.status}`);
        throw new Error(msg || `HTTP ${response.status}`);
      }
      const content = await response.text();
      setFileContent(content);
    } catch (error) {
      console.error('[useFileViewer] Error loading file:', error);
      setFileError(error.message || 'Failed to load file');
    } finally {
      setFileLoading(false);
    }
  }, []);

  const openFolderViewer = useCallback(async (dirPath) => {
    if (!dirPath) return;
    setFileError(null);
    setFileContent('');
    setFolderTree(null);
    setSelectedFilePath('');
    setIsFolderMode(true);
    setFileLoading(true);
    setFileViewerOpen(true);

    try {
      const name = dirPath.split('/').filter(Boolean).pop() || 'Deliverables';
      setFileName(name);
      setFolderPath(dirPath);

      const response = await fetch(`/api/browse/${dirPath}`);
      if (!response.ok) {
        const msg = await response.text().catch(() => `HTTP ${response.status}`);
        throw new Error(msg || `HTTP ${response.status}`);
      }
      const data = await response.json();
      setFolderTree(data.entries);
    } catch (error) {
      console.error('[useFileViewer] Error browsing folder:', error);
      setFileError(error.message || 'Failed to load folder');
    } finally {
      setFileLoading(false);
    }
  }, []);

  const selectFileInFolder = useCallback(async (filePath) => {
    if (!filePath) return;
    setSelectedFilePath(filePath);
    setFileError(null);
    setFileContent('');
    setFileLoading(true);

    try {
      const response = await fetch(`/api/view/${filePath}`);
      if (!response.ok) {
        const msg = await response.text().catch(() => `HTTP ${response.status}`);
        throw new Error(msg || `HTTP ${response.status}`);
      }
      const content = await response.text();
      setFileContent(content);
    } catch (error) {
      console.error('[useFileViewer] Error loading file in folder:', error);
      setFileError(error.message || 'Failed to load file');
    } finally {
      setFileLoading(false);
    }
  }, []);

  const closeFileViewer = useCallback(() => {
    setFileViewerOpen(false);
    setIsFolderMode(false);
    setFolderTree(null);
    setSelectedFilePath('');
  }, []);

  return {
    fileViewerOpen,
    fileContent,
    fileName,
    fileError,
    fileLoading,
    openFileViewer,
    closeFileViewer,
    // Folder browsing
    folderTree,
    folderPath,
    isFolderMode,
    selectedFilePath,
    openFolderViewer,
    selectFileInFolder,
  };
}

export default useFileViewer;
